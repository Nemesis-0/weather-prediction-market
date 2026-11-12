# V3 Configuration

Only non-secret research configuration belongs here.

Current domain-level status is recorded in:

`weather_foreground_status_20261008.json`

Historical frozen configs retain the state that existed at the time of their
freeze. For example, a pre-run status field in a frozen config is provenance,
not the present-tense project status.

Examples of appropriate tracked configuration:

- venue/product allowlists;
- collector parameters;
- weather-source definitions;
- frozen strategy parameters;
- risk / cost assumptions used by a specific frozen protocol;
- research-version identifiers.

Do not commit credentials, session tokens, account identifiers, personal
information, or authentication material.
