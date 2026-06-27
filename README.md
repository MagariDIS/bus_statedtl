# Re-purposing your Kobo: Beyond a Web Browser

If you are feeling disappointed by the performance of your Kobo when browsing the modern web, you are not alone. The current web ecosystem—with its heavy JavaScript, massive advertising scripts, and high memory requirements—often overwhelms the limited hardware of older devices.

However, **do not retire your Kobo just yet.**

The sluggish performance you experience is not a failure of the hardware itself, but a mismatch between a lightweight device and a "heavyweight" web. By shifting your perspective from "a general-purpose computer" to a **"dedicated appliance,"** you can turn your Kobo into a highly functional, specialized tool.

#### The "Single-Task" Philosophy

Instead of struggling to browse the modern internet, why not assign your Kobo to a single, specific mission? By limiting its scope, the device becomes snappy, reliable, and incredibly useful once again:

* **Digital Photo Frame:** A beautiful, low-power display for your favorite memories.
* **Kitchen Companion:** A dedicated interface for displaying your favorite recipes.
* **Smart Home Controller:** A minimalist terminal to toggle lights or check sensors.

When you simplify its role, your Kobo ceases to be a slow browser and transforms into a **"Visible Appliance"**—an elegant, permanent fixture on your desk or in your living room.

Don't let it gather dust in a drawer. Find a dedicated task for it, and let it shine once more.


## Project Example: Kintetsu Bus Arrival Viewer

To demonstrate the "Single-Task" philosophy, I have developed a custom tool to turn the Kobo into a dedicated **Kintetsu Bus Arrival Viewer**.

#### The Problem

The default browser on this Debian-based Kobo (running on an older environment like Ubuntu 13.04) struggles with modern web standards, particularly with TLS certificate validation. Accessing live transit information sites directly is often impossible or unbearably slow.

#### The Solution: A Local Proxy Approach

Instead of fighting the browser, this script acts as a bridge:

1. **Data Fetching:** A Python script runs on the Kobo to fetch and parse the bus arrival data from the Kintetsu Bus official site.
2. **Local Serving:** The script serves a simplified, lightweight HTML page via a local HTTP server (`localhost:8080`).
3. **Visualization:** The Kobo's browser renders only the local, static-like page, avoiding the complexity of modern web scripts.
4. **Automation:** The page automatically refreshes every 60 seconds, ensuring you always have up-to-date arrival times at a glance.

---

## Technical Details

### Requirements

**On your PC (deployment machine):**
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- `ssh` / `scp` commands (OpenSSH client)
- `gh` CLI (optional, for GitHub)

**On the Kobo:**
- Debian/Ubuntu environment with SSH server (Dropbear)
- Python 2.7 or Python 3.x (standard library only — no pip required)
- Firefox or another graphical browser

### Setup

1. Clone this repository on your PC:
   ```bash
   git clone https://github.com/MagariDIS/bus_statedtl.git
   cd bus_statedtl
   uv sync
   ```

2. Create a `.env` file in the project root (never commit this file):
   ```
   KOBO_IP=192.168.x.x
   KOBO_ACCONT=your_username
   KOBO_ACCONT_PASSWORD=your_password
   ```

3. Deploy and launch:
   ```bash
   uv run python main.py
   ```

### File Structure

```
PC (this repo)                       Kobo (/home/<user>/python_apps/bus_statedtl/)
├── main.py          ──SSH/SCP──►   ├── bus_fetch.py
├── bus_fetch.py     ──SCP──────►   ├── bus_server.py
├── bus_server.py    ──SCP──────►   └── config.yaml
├── config.yaml
├── .env             (local only, not committed)
├── pyproject.toml
└── uv.lock
```

### How It Works

**`main.py`** (runs on your PC)
- Reads `KOBO_IP`, `KOBO_ACCONT`, `KOBO_ACCONT_PASSWORD` from `.env`
- Transfers `bus_fetch.py`, `bus_server.py`, and `config.yaml` to the Kobo via `scp`
- Uses legacy SSH key exchange options (`diffie-hellman-group1-sha1`) to connect to the Kobo's old Dropbear SSH server
- Stops any existing server process via `pkill`, then restarts `bus_server.py` in the background
- Opens Firefox on the Kobo via `DISPLAY=:0.0 firefox http://localhost:8080/`

**`bus_server.py`** (runs on the Kobo)
- Starts an HTTP server on port 8080
- On each `GET /` or `GET /?page=N` request, fetches fresh data and returns a rendered HTML page
- Supports multiple route groups defined in `config.yaml`, switchable via page navigation buttons

**`bus_fetch.py`** (runs on the Kobo, also usable standalone)
- Compatible with both Python 2.7 and Python 3.x
- Skips TLS certificate validation via `ssl._create_unverified_context()` to work around the Kobo's outdated SSL stack
- Retrieves the correct current time from the bus site's HTTP `Date` response header (compensates for the Kobo's inaccurate system clock)
- Strips HTML tags and parses bus arrival entries using regex: `N | HH:MM 到着予定 STATUS ... 定刻：HH:MM (delay)`
- Generates a grayscale-optimized card-style HTML layout suited for the Kobo's e-ink-like display

### Route Configuration (`config.yaml`)

Define as many pages and routes as you need. The `YYYYMMDDHHMM` placeholder in each URL is replaced at runtime with the current time.

```yaml
pages:
  - page: "Page label shown in nav button"
    routes:
      - label: "Route A"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
      - label: "Route B"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
  - page: "Another stop"
    routes:
      - label: "Route C"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
```

To find the correct URL for a stop, visit the [Kintetsu Bus arrival info site](https://kintetsu-bus.jorudan.biz/), navigate to your stop, and copy the URL from your browser's address bar. Replace the timestamp portion with `YYYYMMDDHHMM`.

### Local Testing (without a Kobo)

You can run `bus_fetch.py` directly on your PC to verify parsing and HTML output:

```bash
uv run python bus_fetch.py config.yaml
# Output: /tmp/buses.html  (opened automatically in your browser)
```
