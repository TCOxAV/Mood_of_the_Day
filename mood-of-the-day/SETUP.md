# Setup and Running Guide — Mood of the Day (Beta)

This guide provides a comprehensive walk-through on how to install, configure, test, and run **Mood of the Day** on Linux.

> **Note — Beta Testing Notice & Feedback:**
> 
> **Mood of the Day** is currently in **Beta**. The application is being actively tested across various Linux distributions, display servers (Wayland & X11), and desktop environments (GNOME, KDE Plasma, XFCE).
> 
> If you test the application on your system, your feedback is immensely valuable! Please share your experience, report any display/autostart quirks, or request features using our feedback form:
> 
> **Feedback & Testing Form:** [Paste your Google Form link here]

---

## 1. Prerequisites

Make sure you have Python 3.10 or newer installed:

```bash
python3 --version
```

On various Linux distributions, install Python and the required graphics/Qt runtime libraries:

#### Debian / Ubuntu / Linux Mint / Pop!_OS (`apt`)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libegl1 libxkbcommon0 libgl1
```

#### Arch Linux / Manjaro / EndeavourOS (`pacman`)
```bash
sudo pacman -Syu --needed python python-pip libxkbcommon libglvnd
```

#### Fedora / RHEL 9+ / CentOS Stream (`dnf`)
```bash
sudo dnf install -y python3 python3-pip libxkbcommon mesa-libEGL mesa-libGL
```

#### openSUSE (Leap / Tumbleweed) (`zypper`)
```bash
sudo zypper install -y python3 python3-pip libxkbcommon0 libglvnd
```

#### Alpine Linux (`apk`)
```bash
sudo apk add python3 py3-pip libxkbcommon mesa-egl mesa-gles
```

---

## 2. Display Server & Desktop Environment Guide (Wayland, X11, GNOME, KDE, XFCE)

Linux graphics consist of a **display protocol** (Wayland or X11) coupled with a **desktop environment** (GNOME, KDE Plasma, XFCE, etc.).

Check your current session:
```bash
echo "Display Server: $XDG_SESSION_TYPE"   # wayland or x11
echo "Desktop:        $XDG_CURRENT_DESKTOP" # GNOME, KDE, XFCE, etc.
```

PySide6 (Qt 6) automatically detects and adapts to your environment. Here is how it behaves and what to do for each setup:

---

### A. Display Protocol Setup (Wayland vs X11)

#### When using Wayland (Default on modern Fedora, Ubuntu, Debian, Arch)
Wayland runs via Qt’s native `wayland` QPA plugin (`libqwayland.so`).

* **Default Behavior:** Run `python -m mood.main` directly. It connects natively to your Wayland compositor.
* **If you experience fractional scaling or window border quirks:**
  ```bash
  # Force pure native Wayland with client-side decorations
  export QT_QPA_PLATFORM=wayland
  python -m mood.main

  # Or fallback to XWayland compatibility layer
  export QT_QPA_PLATFORM=xcb
  python -m mood.main
  ```

#### When using X11 (Default on Linux Mint, older Ubuntu, XFCE)
X11 runs via Qt’s `xcb` platform plugin.

* **Default Behavior:** Run `python -m mood.main` directly.
* **Troubleshooting:** If Qt reports `Could not load the Qt platform plugin "xcb"`, install the required XCB packages:
  * **Debian / Ubuntu / Mint:** `sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0`
  * **Arch / Manjaro:** `sudo pacman -S --needed libxcb xcb-util-cursor`
  * **Fedora:** `sudo dnf install -y libxcb xcb-util-cursor`

---

### B. Desktop Environment Specifics (GNOME, KDE Plasma, XFCE)

#### 1. GNOME (Coupled with Wayland or X11 — Ubuntu, Fedora, Debian)
* **Autostart:** GNOME automatically reads `~/.config/autostart/*.desktop`. The desktop entry includes `X-GNOME-Autostart-enabled=true`. You can also inspect or toggle it visually via **GNOME Tweaks** (`gnome-tweaks`) under *Startup Applications*.
* **Window Management:** Under GNOME Wayland, the compositor manages window positioning for security; the daily quote popup cleanly centers in your active workspace automatically.
* **Keyring:** GNOME Keyring is usually pre-installed and running via Secret Service DBus API, meaning your API keys are securely encrypted automatically.

#### 2. KDE Plasma (Coupled with Wayland or X11 — Kubuntu, Fedora KDE, openSUSE, Arch)
* **Native Qt Integration:** KDE Plasma is built on Qt, so **Mood of the Day** matches the native system theme, fonts, and dark mode automatically without extra configuration.
* **Autostart:** KDE reads standard XDG desktop entries. You can also view and edit it in **System Settings → Autostart**.
* **Keyring:** KDE Wallet (KWallet) handles secure API key storage. If prompted on first run, allow access to save your keys securely.

#### 3. XFCE (Coupled with X11 — Xubuntu, Linux Mint XFCE, Manjaro XFCE)
* **Display Server:** XFCE runs on X11 (`XDG_SESSION_TYPE=x11`).
* **Autostart:** XFCE fully adheres to XDG autostart. You can manage it visually via **Settings → Session and Startup → Application Autostart**.
* **Keyring:** If GNOME Keyring or KWallet is not installed, the application automatically and safely falls back to a restricted file (`~/.config/mood-of-the-day/keys.json` with user-only `0600` permissions).

---

### Headless & Remote Testing (All Environments)
If testing over SSH, in Docker, or via CI without an active monitor:
```bash
export QT_QPA_PLATFORM=offscreen
pytest
```

---

## 3. Environment Setup

From the root of the repository (`mood-of-the-day`):

### Option A: Create a Dedicated Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate
```

### Option B: Using an Existing Virtual Environment

If you already created a virtual environment outside or inside the project, activate it:

```bash
source path/to/venv/bin/activate
```

---

## 4. Install Dependencies

Install the package in editable mode along with development and test dependencies:

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

Alternatively, install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 5. Run the Test Suite

Run pytest to verify that all components, quotes validation, rolling cache, and provider mocks pass:

```bash
pytest
```

To run with coverage reporting:

```bash
pytest --cov=mood --cov-report=term-missing
```

---

## 6. Running the Application

Launch the desktop application:

```bash
python -m mood.main
```

Or via the installed console entry point:

```bash
mood-of-the-day
```

---

## 7. What Happens on First Launch

1. **Setup Wizard**:
   - Prompts for your name (how the app greets you).
   - Prompts for optional API keys (OpenAI and/or Google Gemini). *You can skip this to use the app in offline fallback mode.*
   - Prompts for your personality, interests, preferred tone, and favorite themes (e.g., `stoicism, curiosity, science`).
2. **Daily Quote Popup**:
   - Shows your personalized daily quotation with author, source, and AI commentary.
   - Includes interactive feedback controls:
     - **👍 Like**: Positively reinforces the author/themes.
     - **👎 Not for me**: Decreases the frequency of similar quotes.
     - **🔄 New quote**: Regenerates today's quote on demand.
     - **⚙ Settings**: Lets you update your profile, add/test API keys, reset learning data, or clear cache.

---

## 8. Configuring Linux Autostart (On Login)

### Method 1: Using the Settings UI
1. Click the **⚙** gear icon on the daily popup.
2. In the **Profile** tab, check **"Start automatically on login"**.
3. Click **Save Changes**.

### Method 2: Using the Installation Script
```bash
./scripts/install.sh
```

To remove the autostart entry:
```bash
./scripts/uninstall.sh
```

---

## 9. Running in Docker (Optional)

The project includes a [`Dockerfile`](Dockerfile) for running the Linux desktop app in a container. These commands assume Docker Engine is installed and that you are running them from the project directory.

### 1. Build the Docker Image

Build the image using your host user and group IDs. This lets the container access your mounted profile and configuration files without making them root-owned:

```bash
docker build \
  --build-arg USER_UID="$(id -u)" \
  --build-arg USER_GID="$(id -g)" \
  -t mood-of-the-day:latest .
```

Create the host directories used to persist the profile, quote cache, and settings:

```bash
mkdir -p "$HOME/.local/share/mood-of-the-day" "$HOME/.config/mood-of-the-day"
```

### 2. Run the Application

#### X11 or XWayland

Run this from a terminal in your desktop session. The temporary X11 permission is removed after the container exits.

```bash
CURRENT_USER="$(id -un)"
xhost "+SI:localuser:$CURRENT_USER"
docker run -it --rm \
  -e DISPLAY="$DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "$HOME/.local/share/mood-of-the-day:/home/appuser/.local/share/mood-of-the-day" \
  -v "$HOME/.config/mood-of-the-day:/home/appuser/.config/mood-of-the-day" \
  mood-of-the-day:latest
xhost "-SI:localuser:$CURRENT_USER"
```

The container starts the app automatically. The mounted directories keep your profile, quote cache, and configuration between runs.

#### Native Wayland

Run this from a terminal in your Wayland desktop session. The host and container must be able to access the socket; the image build above matches the container user's UID and GID to your host user.

```bash
docker run -it --rm \
  -e XDG_RUNTIME_DIR=/tmp \
  -e WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
  -e QT_QPA_PLATFORM=wayland \
  -v "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY:/tmp/$WAYLAND_DISPLAY:ro" \
  -v "$HOME/.local/share/mood-of-the-day:/home/appuser/.local/share/mood-of-the-day" \
  -v "$HOME/.config/mood-of-the-day:/home/appuser/.config/mood-of-the-day" \
  mood-of-the-day:latest
```

#### Run Tests Without a GUI

The image includes the project's test dependencies. Override its default app command to run the test suite headlessly:

```bash
docker run --rm \
  -e QT_QPA_PLATFORM=offscreen \
  mood-of-the-day:latest python -m pytest
```
