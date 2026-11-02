from pathlib import Path
import requests

out = Path(r"C:\Users\HomePC\Documents\Default Project\pdf-studio\assets\fonts")
out.mkdir(parents=True, exist_ok=True)
ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"}

files = {
    "clash-grotesk-400.ttf": "https://cdn.fontshare.com/wf/O462VY6O6FTQCS72XVMTQHXAM4NN5CY3/TWF57ITZORMJ3MEWLQQIVO6BMXIB6FUR/MJQFMMOTEGNXDVM7HBBDTQHTVB2M7Y6G.ttf",
    "clash-grotesk-500.ttf": "https://cdn.fontshare.com/wf/2SAK53YLUN7RMYJU4MYLSBV6SSSJEJZB/RXS4DPGJRKOUFZMF5X5BVUGNNKJT65XZ/DJS4RYGIUYUXJQOHY5VCZPKSTXUSHTSP.ttf",
    "Manrope.ttf": "https://github.com/google/fonts/raw/main/ofl/manrope/Manrope%5Bwght%5D.ttf",
    "Fraunces.ttf": "https://github.com/google/fonts/raw/main/ofl/fraunces/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf",
    "SourceSerif4.ttf": "https://github.com/google/fonts/raw/main/ofl/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf",
    "SpaceGrotesk.ttf": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
}

for name, url in files.items():
    try:
        r = requests.get(url, headers=ua, timeout=60)
        r.raise_for_status()
        (out / name).write_bytes(r.content)
        print(name, len(r.content) // 1024, "KB")
    except Exception as exc:
        print(name, "FAILED", exc)
