# 0 Architectural refactor of ceit.py in `owi-metadatabase-results-sdk`

Currently, `analyses/ceit.py` and `plotting/ceit.py`, contain a mix of functions for building payloads, making API calls, and processing results for the specific usecase of CEIT data. Consequently, there is a services/ceit.py file that imports `analyses/ceit.py` and `plotting/ceit.py` to build the backend analysis and results, and then plot them. This structure is not ideal for maintainability and scalability.

I prefer the currently implemented structure of analyses/lifetime_design_frequencies.py, analyses/lifetime_design_verification.py, and analyses/wind_speed_histogram.py, that adopts a more general structure for uploading and fetching analyses and results, and plotting them. The specific use case logic is contained in the notebook under scripts/, while the backend logic is contained in the analyses/ folder, and the plotting logic is contained in the plotting/ folder. The services/ceit.py file could probably disappear, and the whole logic should be contained in the analyses/ceit.py and plotting/ceit.py files, that should be refactored to contain more general functions for building payloads, making API calls, and processing results for CEIT data.

Implement a similar structure for the CEIT use case, by refactoring the existing code in analyses/ceit.py and plotting/ceit.py, and moving the specific use case logic to the notebook under scripts/, that should be renamed to 4.1.ceit-corrosion-monitoring-simplified.ipynb.

See also the notebook in scripts/1.0.lifetime-design-frequencies.ipynb for an example of how to structure the notebook and the code.

Code refactoring should use the python SKILL, and documentation shold use the documentation-writer and the zensical SKILLs.

# 1 Add static plots to the notebooks in the scripts/ folder

I am running the notebooks in the scripts/ folder for verification. I have the following comments:

* legend in #sym:comparison_plot should be multi column and outside of plot
* x-axis tick labels orientation in #sym:location_plot  shall be vertical
* plots in #sym:location_plot  shall be only markers
* all plots shall use monospace by default
* Units in axes shall not be enxapsulated in square brackets, but after a comma.
  Example: Frequency [Hz] -> Frequency, Hz
* This warning should be removed from the output: `/home/pietro.dantuono@24SEA.local/Projects/SMARTLIFE/OWI-metadatabase-SDK/owi-metadatabase-results-sdk/.venv/lib/python3.13/site-packages/IPython/core/events.py:100: UserWarning: constrained_layout not applied because axes sizes collapsed to zero.  Try making figure larger or Axes decorations smaller.`

# 2 Bugfix(`owi-metadatabase-results-sdk`)

> [!IMPORTANT] There is currently no way to link a Sensor type of object to a Result for CEIT type of data.
> `build_sensor_results` in `services/ceit.py` expects only Signal instead of Signal/Sensor as a
> `related_object`, see line 140 in `services/ceit.py#L140`.
