# ShopGuard AI — Physical CCTV & NVR Setup Guide

This guide explains how to connect your commercial store cameras, DVRs, or NVRs to **ShopGuard AI** for automated local intrusion detection.

---

## 1. Supported Camera Types

ShopGuard AI supports standard **H.264 / H.265 RTSP streams** across all major camera manufacturers:

- **Standalone IP Cameras**: Direct connection via Wi-Fi or Ethernet.
- **NVRs (Network Video Recorders)**: Connecting to multi-camera channels on a central NVR.
- **DVRs (Digital Video Recorders)**: Connecting to analog cameras connected to a modern hybrid/network DVR.
- **Local Laptop Webcam**: A dedicated development/simulation source (`--webcam`) for off-site testing without physical CCTV hardware.

> [!NOTE]
> Analog BNC CCTV cameras cannot connect directly over IP without being plugged into a networked DVR or video encoder that produces an RTSP stream.

---

## 2. Common RTSP Stream Paths by Manufacturer

Most security cameras use standardized stream path patterns:

| Brand | Default RTSP Port | Primary Main-Stream Path (1080p/4K) | Sub-Stream Path (Low Bandwidth) |
| :--- | :---: | :--- | :--- |
| **Hikvision / Annke** | `554` | `/Streaming/Channels/101` | `/Streaming/Channels/102` |
| **Dahua / Amcrest** | `554` | `/cam/realmonitor?channel=1&subtype=0` | `/cam/realmonitor?channel=1&subtype=1` |
| **Reolink** | `554` | `/h264Preview_01_main` | `/h264Preview_01_sub` |
| **Uniview (UNV)** | `554` | `/unicast/c1/s0/live` | `/unicast/c1/s1/live` |
| **Axis Communications** | `554` | `/axis-media/media.amp` | `/axis-media/media.amp?videocodec=h264` |
| **TP-Link Tapo / Vigi** | `554` | `/stream1` | `/stream2` |
| **Generic ONVIF / DVR** | `554` | `/live/ch0` or `/ch1/main` | `/live/ch0_sub` |

---

## 3. Step-by-Step Connection Instructions

### Step 1: Assign a Static IP or DHCP Reservation
1. Log in to your store's Wi-Fi router or network switch admin console.
2. Find the camera's MAC address and assign a **DHCP Reservation** or **Static IP** (e.g., `192.168.1.150`).
3. Ensure your Windows ShopGuard AI PC and the cameras are on the same local subnet.

### Step 2: Enable RTSP in Camera Settings
1. Open your camera's web configuration interface in a browser (e.g. `http://192.168.1.150`).
2. Navigate to **Network → Advanced Settings → Integration Protocol** or **Port Settings**.
3. Verify that **RTSP** is enabled and port is set to `554`.
4. Ensure you have created a dedicated user account (e.g., `shopguard` with a strong password).

### Step 3: Add the Camera in the Mobile App
1. Open the **ShopGuard AI Android App**.
2. Tap the **Cameras** tab in the bottom navigation bar.
3. Tap the floating **Add New Camera** button.
4. Fill in the details:
   - **Camera Name**: e.g., `Cash Drawer Front View`
   - **Camera Type**: Select `IP Camera`, `DVR`, or `NVR`.
   - **IP Address**: Enter `192.168.1.150`.
   - **RTSP Port**: `554`.
   - **Username**: `admin` (or dedicated user).
   - **Password**: Enter camera password (tap the eye icon to verify).
   - **Stream Path**: Enter your camera's path (e.g. `/Streaming/Channels/101` or `/live/ch0`).
   - **Location**: e.g., `Checkout Counter 1`.
5. Tap **TEST PROBE**.
   - ShopGuard AI will test network reachability and decode a sample video frame.
   - When verified, a green banner confirms resolution, framerate, and latency.
6. Tap **ADD CAMERA**.
7. The camera immediately starts streaming to the background AI engine without restarting the agent!

---

## 4. Troubleshooting Checklist

| Issue | Likely Cause | Solution |
| :--- | :--- | :--- |
| **"Socket connect timeout"** | Camera is powered off or IP is wrong | Verify camera power and ping the IP from your Windows PC terminal (`ping 192.168.1.150`). |
| **"Handshake failed / 401"** | Incorrect username or password | Re-type credentials or check camera web admin to verify permissions. |
| **"Frame decoding failed"** | Unsupported codec or wrong stream path | Set camera video encoding to **H.264 Baseline or Main Profile** in camera web settings. |
| **"Duplicate Camera"** | Channel already added | Check the Cameras list. To modify settings, tap the **Pencil icon** on the existing card. |

---

## 5. Security Best Practices

1. **Keep Cameras on an Isolated VLAN**: Place security cameras and the ShopGuard AI host on a dedicated IoT/Security VLAN without direct inbound port forwarding from the public internet.
2. **Never Expose Port 554 to the WAN**: The ShopGuard AI Windows PC ingests RTSP feeds locally; the mobile app connects to the ShopGuard API over local Wi-Fi.
3. **Use Dedicated Accounts**: Avoid using default `admin / admin` credentials. Create a separate read-only operator account for ShopGuard AI stream ingestion.
