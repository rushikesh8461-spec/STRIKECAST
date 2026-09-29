# Model comparison

Status: **NOT RUN — NO VALID REAL SPLITS**. Climatology, persistence, classical baselines, and ConvLSTM must use the same observed-target mask and chronological test split. Neither exists for the current uploads. No validation winner or test metric was selected. The currently served model remains `DEMO_ONLY`.

The existing validation baseline runner now passes target masks to baselines and evaluates only observed validation cells. It must not be invoked until the strict real dataset contract passes.
