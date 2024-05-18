# VR programme
## Configuration
Configuration files are stashed under the folder `config` and take up a _JSON_ format.
These configuration files define the main behavioural task, and at the start of the programme, the user is prompted to select which configuration to load.
There are four main parameters fields:
* `"settings":` Main settings for programme **Note: you can set global settings for contexts here which will override the individual settings defined in** `"contexts"`
  * `"voltage_scale" -> [float, float]` The lower and upper range of voltages corresponding to the beginning and end positions of the track,
  * `"gain" -> float` VR gain,
  * `"assets_path" -> string` Path to assets folder,
  * `"save_path" -> string` Path to folder where CSV data files should be saved.
* `"contexts":`
  * `"": {} -> string` Give a name to each context
    * `"brake" -> bool` Whether to apply the brake,
    * `"env" -> float` Length of the environment (AKA trial end location),
    * `"splash" -> string/null` Image file for the splash/cue screen displayed at the beginning, set `null` to disable splash screen,
    * `"splash_dur" -> float` Duration of splash screen in seconds,
    * `"rewards" -> list of floats` Locations of rewards,
    * `"reward_dur" -> float` Duration of each reward (how long to pump) in seconds,
    * `"sound" -> string/null` Sound file to play at reward, set `null` to disable sound,
    * `"sound_dur" -> float` Duration of sound in seconds,
    * `"trial_delay" -> float`
* `"sequence":`
* `"channels":`
