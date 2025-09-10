# skyfall

Skyfall is a toolkit for wireless drone analysis, exploitation, and post-exploitation tasks.

## Getting Started

1. **Install the drivers for your WiFi card.**  
   Example: RTL8821AU chipset  
   Reference Links:  
   - [aircrack-ng/rtl8812au](https://github.com/aircrack-ng/rtl8812au?tab=readme-ov-file)  
   - [lwfinger/rtw88](https://github.com/lwfinger/rtw88)

## Directory Structure

- **src/**  
  Main source code folder.
  - **main.py**: Entry point for the toolkit.
  - **console/**: Console interface and banner display.
    - `interface.py`: Command-line interface logic.
    - `show_banner.py`: Displays project banner.
  - **external_dependencies/**: Third-party integrations and wrappers.
  - **hardware_handler/**: Handles hardware interactions (WiFi cards, etc.).
  - **modules/**: Core modules for scanning, exploitation, and post-exploitation.
    - `post/`: Scripts for post-exploitation (memory dump, log extraction, persistence).
  - **shared/**: Shared utilities and resources.

- **airodump_results/**  
  Stores output CSV files from airodump-ng scans.

- **.vscode/**  
  VSCode editor configuration.

- **ap_data.txt, context.json, sniff.pcap, drone_video_capture.mp4**  
  Example data files and captures.

- **README.md**  
  Project documentation.

- **requirements.txt**  
  Python dependencies.

## Project Plan

1. Identify and list WiFi interfaces; switch to monitor mode.
2. Capture traffic, identify drones by MAC/name, enhance with behavioral analysis.
3. Deauthenticate, crack password, connect to device.
4. Send control signals.
5. Capture camera feed.
6. Scan for open ports/vulnerabilities.
7. Post-exploitation: install backdoor/malware (like Metasploit).

## Docker Setup

Run the following for privileged access to host devices:
```sh
docker run -it --net=host --privileged ubuntu bash
```
Helpful when you want to run the tool inside a docker container

## Tool Dependencies

- aircrack-ng
- mdk4
- ffmpeg

## Notes

- See [`src/modules/post/notes.txt`](src/modules/post/notes.txt) for post-exploitation ideas.
- [`src/hardware_handler/notes.txt`](src/hardware_handler/notes.txt) contains hardware handler refactoring