from dataclasses import dataclass
from datetime import datetime

from core.entities.instrument import Instrument
from core.market_data.historical_coverage import TimeRange
from core.market_data.provider_instrument_binding import (
    ProviderInstrumentBinding,
    ResolvedProviderBinding,
    resolve_provider_bindings,
)


class InstrumentRegistryError(ValueError):
    """Canonical instrument or provider-binding resolution failed."""


def _require_nonempty_string(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


def _is_aware(value: datetime) -> bool:
    return value.utcoffset() is not None


def _instrument_applies_at(
    instrument: Instrument,
    at: datetime,
) -> bool:
    for boundary in (
        instrument.effective_from,
        instrument.effective_to,
    ):
        if boundary is None:
            continue

        if _is_aware(boundary) != _is_aware(at):
            raise InstrumentRegistryError(
                "instrument effective bounds and resolution time "
                "timezone awareness must match"
            )

    if (
        instrument.effective_from is not None
        and at < instrument.effective_from
    ):
        return False

    if (
        instrument.effective_to is not None
        and at >= instrument.effective_to
    ):
        return False

    return True


@dataclass(frozen=True)
class StaticInstrumentRegistry:
    """
    Immutable canonical-instrument and provider-binding registry.

    This class owns deterministic resolution mechanics only. It does
    not manufacture production instrument identities or provider
    bindings. Application composition must supply those values from an
    explicit source with defensible temporal provenance.
    """

    instruments: tuple[Instrument, ...]
    provider_bindings: tuple[ProviderInstrumentBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.instruments, tuple):
            raise TypeError(
                "instruments must be a tuple"
            )

        if not isinstance(
            self.provider_bindings,
            tuple,
        ):
            raise TypeError(
                "provider_bindings must be a tuple"
            )

        if any(
            not isinstance(value, Instrument)
            for value in self.instruments
        ):
            raise TypeError(
                "instruments must contain Instrument values"
            )

        if any(
            not isinstance(
                value,
                ProviderInstrumentBinding,
            )
            for value in self.provider_bindings
        ):
            raise TypeError(
                "provider_bindings must contain "
                "ProviderInstrumentBinding values"
            )

        binding_ids = tuple(
            value.binding_id
            for value in self.provider_bindings
        )

        if len(binding_ids) != len(set(binding_ids)):
            raise InstrumentRegistryError(
                "provider binding identity is duplicated"
            )

        known_instrument_ids = {
            value.instrument_id
            for value in self.instruments
        }

        if any(
            value.instrument_id not in known_instrument_ids
            for value in self.provider_bindings
        ):
            raise InstrumentRegistryError(
                "provider binding references unknown "
                "canonical instrument"
            )

    def resolve_symbol(
        self,
        *,
        symbol: str,
        exchange: str,
        at: datetime,
    ) -> Instrument:
        """
        Resolve one symbol/exchange observation to canonical identity.

        Instrument effective intervals use half-open semantics:
        [effective_from, effective_to).
        """

        _require_nonempty_string(
            symbol,
            "symbol",
        )
        _require_nonempty_string(
            exchange,
            "exchange",
        )

        if not isinstance(at, datetime):
            raise TypeError(
                "at must be a datetime"
            )

        matches = tuple(
            value
            for value in self.instruments
            if (
                value.symbol == symbol
                and value.exchange == exchange
                and _instrument_applies_at(
                    value,
                    at,
                )
            )
        )

        if not matches:
            raise InstrumentRegistryError(
                "canonical instrument could not be resolved"
            )

        if len(matches) != 1:
            raise InstrumentRegistryError(
                "canonical instrument resolution is ambiguous"
            )

        return matches[0]

    def bindings_for(
        self,
        *,
        instrument_id: str,
        provider: str,
    ) -> tuple[ProviderInstrumentBinding, ...]:
        """
        Return deterministic candidate bindings for one pair.

        This method does not assert temporal coverage. Call
        resolve_bindings() for a concrete historical request.
        """

        _require_nonempty_string(
            instrument_id,
            "instrument_id",
        )
        _require_nonempty_string(
            provider,
            "provider",
        )

        return tuple(
            sorted(
                (
                    value
                    for value in self.provider_bindings
                    if (
                        value.instrument_id
                        == instrument_id
                        and value.provider
                        == provider
                    )
                ),
                key=lambda value: value.binding_id,
            )
        )

    def resolve_bindings(
        self,
        *,
        instrument_id: str,
        provider: str,
        request: TimeRange,
    ) -> tuple[ResolvedProviderBinding, ...]:
        """
        Resolve exact effective-dated provider subranges.

        Gap, overlap, ambiguity and timezone-awareness semantics remain
        owned by the accepted M9.3 provider-binding resolver.
        """

        return resolve_provider_bindings(
            instrument_id=instrument_id,
            provider=provider,
            request=request,
            bindings=self.bindings_for(
                instrument_id=instrument_id,
                provider=provider,
            ),
        )
