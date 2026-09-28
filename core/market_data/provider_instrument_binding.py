from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from core.market_data.historical_coverage import TimeRange


def _is_aware(value: datetime) -> bool:
    return value.utcoffset() is not None


def _require_non_empty_string(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class ProviderInstrumentBinding:
    """Immutable mapping from canonical instrument identity to a provider."""

    binding_id: str
    instrument_id: str
    provider: str
    provider_instrument_id: str
    provider_exchange: str | None = None
    provider_segment: str | None = None
    provider_symbol: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string("binding_id", self.binding_id)
        _require_non_empty_string("instrument_id", self.instrument_id)
        _require_non_empty_string("provider", self.provider)
        _require_non_empty_string(
            "provider_instrument_id",
            self.provider_instrument_id,
        )

        optional_strings = {
            "provider_exchange": self.provider_exchange,
            "provider_segment": self.provider_segment,
            "provider_symbol": self.provider_symbol,
        }
        for name, value in optional_strings.items():
            if value is not None and (
                not isinstance(value, str) or not value
            ):
                raise ValueError(
                    f"{name} must be a non-empty string or None"
                )

        if self.effective_from is not None and not isinstance(
            self.effective_from,
            datetime,
        ):
            raise TypeError(
                "effective_from must be a datetime or None"
            )

        if self.effective_to is not None and not isinstance(
            self.effective_to,
            datetime,
        ):
            raise TypeError(
                "effective_to must be a datetime or None"
            )

        if (
            self.effective_from is not None
            and self.effective_to is not None
        ):
            if _is_aware(self.effective_from) != _is_aware(
                self.effective_to
            ):
                raise ValueError(
                    "binding effective bounds must use matching "
                    "timezone awareness"
                )

            if self.effective_from >= self.effective_to:
                raise ValueError(
                    "binding effective_from must be before effective_to"
                )


@dataclass(frozen=True)
class ResolvedProviderBinding:
    binding: ProviderInstrumentBinding
    applied_range: TimeRange


class ProviderBindingResolutionError(ValueError):
    pass


def _validate_request_awareness(
    request: TimeRange,
    binding: ProviderInstrumentBinding,
) -> None:
    request_aware = _is_aware(request.start)

    for boundary in (
        binding.effective_from,
        binding.effective_to,
    ):
        if boundary is None:
            continue

        if _is_aware(boundary) != request_aware:
            raise ProviderBindingResolutionError(
                "provider binding and request timezone awareness "
                "must match"
            )


def _intersection(
    request: TimeRange,
    binding: ProviderInstrumentBinding,
) -> TimeRange | None:
    start = request.start

    if (
        binding.effective_from is not None
        and binding.effective_from > start
    ):
        start = binding.effective_from

    end = request.end

    if (
        binding.effective_to is not None
        and binding.effective_to < end
    ):
        end = binding.effective_to

    if start >= end:
        return None

    return TimeRange(start=start, end=end)


def resolve_provider_bindings(
    instrument_id: str,
    provider: str,
    request: TimeRange,
    bindings: Iterable[ProviderInstrumentBinding],
) -> tuple[ResolvedProviderBinding, ...]:
    """
    Resolve exact provider-binding subranges for one requested period.

    Binding intervals use half-open semantics where both bounds exist.
    Open-ended bounds are permitted.
    """

    _require_non_empty_string("instrument_id", instrument_id)
    _require_non_empty_string("provider", provider)

    if not isinstance(request, TimeRange):
        raise TypeError("request must be a TimeRange")

    applicable: list[
        tuple[TimeRange, ProviderInstrumentBinding]
    ] = []
    seen_binding_ids: set[str] = set()

    for binding in bindings:
        if not isinstance(binding, ProviderInstrumentBinding):
            raise TypeError(
                "bindings must contain ProviderInstrumentBinding values"
            )

        if binding.binding_id in seen_binding_ids:
            raise ProviderBindingResolutionError(
                "provider binding identity is duplicated"
            )
        seen_binding_ids.add(binding.binding_id)

        if (
            binding.instrument_id != instrument_id
            or binding.provider != provider
        ):
            continue

        _validate_request_awareness(request, binding)

        applied_range = _intersection(request, binding)
        if applied_range is not None:
            applicable.append((applied_range, binding))

    applicable.sort(
        key=lambda item: (
            item[0].start,
            item[0].end,
            item[1].binding_id,
        )
    )

    resolved: list[ResolvedProviderBinding] = []
    cursor = request.start

    for applied_range, binding in applicable:
        if applied_range.start > cursor:
            raise ProviderBindingResolutionError(
                "provider binding coverage has a gap"
            )

        if applied_range.start < cursor:
            raise ProviderBindingResolutionError(
                "provider binding coverage has a conflicting overlap"
            )

        resolved.append(
            ResolvedProviderBinding(
                binding=binding,
                applied_range=applied_range,
            )
        )
        cursor = applied_range.end

    if cursor < request.end:
        raise ProviderBindingResolutionError(
            "provider binding coverage has a gap"
        )

    if not resolved:
        raise ProviderBindingResolutionError(
            "provider binding coverage has a gap"
        )

    return tuple(resolved)
