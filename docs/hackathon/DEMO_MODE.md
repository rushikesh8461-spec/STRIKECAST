# DEMO mode

`STRIKECAST_MODE=DEMO` is the local default. It uses a fixed reference timestamp, coordinate-seeded synthetic atmospheric records, the checksum-pinned synthetic-trained ConvLSTM, provisional risk policy and explicitly labeled lightning presentation simulation. Repeated requests for the same location are deterministic.

DEMO data and model output do not represent observations or forecast skill. The atmospheric provider's LIVE data path is not automatically contacted by the serving API. Never use demo output for safety decisions.
