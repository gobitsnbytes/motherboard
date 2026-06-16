# BITS&BYTES Discord Role Hierarchy & Access Control

This document defines the structured role hierarchy, permission system, and Discord Role IDs implemented across the Bits&Bytes Discord Bot and Notion integration.

---

## 📊 Visual Role Hierarchy Diagram

```mermaid
graph TD
    %% Global Admins
    subgraph Global Administration
        admin["Administrator / Owner<br/>ID: 1480620981587279993"]
        exec["Executive Leadership / HQ Role<br/>(Full Access to All Forks)<br/>IDs: 1506019032015310949, 1509256369994203146"]
        dept["Department Lead Role<br/>(Full Access to All Forks)<br/>ID: 1506323726223016149"]
    end

    %% Global Contributors
    subgraph Global Contributors / Parent Tracks
        contrib["@Contributor Role<br/>(General Access)<br/>ID: 1506019068132462804"]
        track["Global Track Roles<br/>(tech, creative, ops, outreach)<br/>(Cross-Fork VIEW Access Only)"]
    end

    %% Fork Local Levels
    subgraph Local Fork Level (City-Specific)
        city["City Role (e.g., delhi)<br/>(Community Level)"]
        cityContrib["Contributor City Role (e.g., contributor-delhi)<br/>(Fork Member Access)"]
        
        subgraph Local Hierarchy (Requires @Contributor + City + Contributor City)
            forkLead["Fork Lead / @fork-lead<br/>(Full City-Level Modify/View)<br/>ID: 1490410901147488286"]
            localTrack["Fork Track Lead Roles<br/>(tech-lead, creative-lead, ops-lead, outreach-lead)<br/>(Modify Specific Track Only)<br/>IDs: 1509224755595841676, 1509224757579616276, 1509224760293195927, 1509224762906247178"]
            forkContrib["Fork Contributor<br/>(City-Specific VIEW Only)"]
        end
    end

    %% Connectors
    admin --> exec
    exec --> dept
    dept --> contrib
    contrib --> track
    contrib --> cityContrib
    city --> cityContrib
    
    %% Fork roles need the intersection
    cityContrib --> forkLead
    cityContrib --> localTrack
    cityContrib --> forkContrib
```

---

## 🧬 Core Role Configuration Mapping

### 1. Global Administrative Roles (HQ & Staff)
These roles hold full, global permissions to read and modify all server resources, Notion data, and bot configurations.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose / How Assigned |
| :--- | :--- | :--- | :--- | :--- |
| `admin` | `1480620981587279993` | `#f1c40f` (Gold) | No | **Administrator**: Full server and guild owner status. |
| `Executive Leadership` | `1506019032015310949` | `#97192c` (Burgundy) | Yes | **Executive Team**: Full server and database operations control. |
| `Department Leads` | `1506323726223016149` | `#fc920d` (Orange) | Yes | **Global Track Leadership**: Oversight of all organization tracks. |
| `hq` | `1509256369994203146` | `#f1c40f` (Gold) | Yes | **Foundation Core**: Manually assigned to Bits&Bytes Foundation members. |

### 2. Fork Track Lead Roles
These roles represent the track leads of individual city forks (e.g., Bangalore Tech Lead, Delhi Ops Lead). The bot automatically assigns these roles to fork members based on their Notion role.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `tech-lead` (or `Tech Lead`) | `1509224755595841676` | `#1f8b4c` (Emerald Green) | Yes | **Tech Lead**: Leads the tech track inside their city fork. |
| `creative-lead` (or `Creative Lead`) | `1509224757579616276` | `#ad1457` (Magenta) | Yes | **Creative Lead**: Leads the creative/design track inside their city fork. |
| `ops-lead` (or `Ops Lead`) | `1509224760293195927` | `#11806a` (Teal) | Yes | **Ops Lead**: Leads the operations track inside their city fork. |
| `outreach-lead` (or `Outreach Lead`) | `1509224762906247178` | `#a84300` (Orange/Rust) | Yes | **Outreach Lead**: Leads the outreach track inside their city fork. Also acts as a Global Department Lead. |

### 3. Base Contributor & Global Track Roles
These roles represent base membership and global track-specific capabilities without local city restrictions.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `Contributor` | `1506019068132462804` | `#00ff94` (Bright Green) | Yes | **Base Contributor**: Auto-granted to all onboarded members. |
| `Builder` | `1480624226414366924` | `#3498db` (Light Blue) | Yes | **Legacy/General Contributor**: Builder role mapping. |
| `tech` | `1509224750663073865` | `#3498db` (Blue) | Yes | **Global Tech Contributor**: General parent developer track. |
| `creative` | `1490412912420847646` | `#eb459e` (Pink) | No | **Global Creative Contributor**: General parent design track. |
| `ops` | `1490413018830471332` | `#eb459e` (Pink) | No | **Global Ops Contributor**: General parent operations track. |
| `outreach` | `1509224752747909351` | `#e67e22` (Orange) | Yes | **Global Outreach Contributor**: General parent outreach track. |

### 4. Local Fork Lead Roles
These roles manage single city forks (e.g. Delhi, Mumbai, Bangalore).

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `fork-lead` | `1490410901147488286` | `#7289da` (Blurple) | Yes | **City Fork Lead**: Leading a city fork. |

### 5. Local Fork Contributor Identity Roles
These roles are assigned to identify contributors mapped to specific city forks.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `contributor-Bangalore` | `1508766945091260436` | `#000000` | No | Contributor identity for Bangalore. |
| `contributor-Hyderabad` | `1508767008660000840` | `#000000` | No | Contributor identity for Hyderabad. |
| `contributor-Noida` | `1508767019745677394` | `#000000` | No | Contributor identity for Noida. |
| `contributor-Kolkata` | `1508767029593899160` | `#000000` | No | Contributor identity for Kolkata. |
| `contributor-Jaipur` | `1508767044567306310` | `#000000` | No | Contributor identity for Jaipur. |
| `contributor-Solan` | `1508767065308135525` | `#000000` | No | Contributor identity for Solan. |
| `contributor-Beawar` | `1508767089081450587` | `#000000` | No | Contributor identity for Beawar. |

### 6. Local City Roles (Community Members)
These roles are public/community identity roles for members belonging to specific cities.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `delhi` | `1490411548752085094` | `#5865f2` | No | Delhi community role. |
| `mumbai` | `1490411614292283552` | `#5865f2` | No | Mumbai community role. |
| `chennai` | `1490411705983832325` | `#5865f2` | No | Chennai community role. |
| `kanpur` | `1490411774472753198` | `#5865f2` | No | Kanpur community role. |
| `other-city` | `1490411854189822112` | `#000000` | No | Generic fallback city role. |
| `lucknow` | `1490411988902477824` | `#000000` | No | Lucknow community role. |
| `bangalore` | `1490412532152930315` | `#5865f2` | No | Bangalore community role. |
| `hyderabad` | `1490412746951626752` | `#5865f2` | No | Hyderabad community role. |
| `kolkata` | `1490413148543385822` | `#5865f2` | No | Kolkata community role. |
| `Noida` | `1508052355579641856` | `#000000` | No | Noida community role. |
| `Jaipur` | `1508052382229987470` | `#000000` | No | Jaipur community role. |
| `Solan` | `1508052399338688613` | `#000000` | No | Solan community role. |
| `Beawar` | `1508052414215749683` | `#000000` | No | Beawar community role. |
| `"your-city-name"` | `1508199356077965424` | `#000000` | No | Template city role (hyphenated). |
| `"your city name"` | `1508199867372015616` | `#000000` | No | Template city role (spaced). |
| `example` | `1508200326648565794` | `#000000` | No | Example city role. |

### 7. Managed & Integration Roles
These roles are managed directly by integrations or external bots, and cannot be modified by other roles.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `Bits&Bytes` (Bot integration) | `1490425472570495210` | `#71368a` | Yes | Primary Bot execution identity role. |
| `Wick` | `1480633459864240264` | `#000000` | No | Wick Security Bot integration role. |
| `AutoMod` | `1480624666610766101` | `#000000` | No | Discord AutoMod system role. |
| `DISBOARD.org` | `1505612966291177492` | `#000000` | No | Disboard bump bot integration. |
| `carl-bot` | `1505995557699584192` | `#000000` | No | Carl-bot helper integration. |
| `Embed Generator` | `1506005487936864288` | `#000000` | No | Embed generator bot integration. |
| `Logger` | `1506019693272502585` | `#000000` | No | Logging bot integration. |
| `Bits&Bytes` (Instance B) | `1510233907008901183` | `#000000` | No | Secondary instance integration. |
| `Bits&Bytes` (Instance C) | `1510234383020458004` | `#000000` | No | Tertiary instance integration. |

### 8. Miscellaneous / Low Roles

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `[Nerds]` | `1480637320699973807` | `#e74c3c` (Red) | Yes | Community badge role. |
| `Quarantine` | `1480633565510369332` | `#b38844` | No | Security quarantine role. |
| `research` | `1490413663239278592` | `#eb459e` | No | Research track role. |
| `muted` | `1490816011727933622` | `#f4424b` | No | Text/voice muted role. |
| `Discord Maintainer` | `1506341723964571868` | `#000000` | No | Server helper role. |
| `dev` | `1510220403573002240` | `#000000` | No | Development testing role. |

---

## 🔒 Granular Access Control & Permissions Matrix

The authentication engine evaluates command permissions and Notion access rules through nested logic gates.

### 1. Global Admins (HQ, Executive Leadership, Staff)
*   **Identification**: Holds Server Admin permissions, `STAFF_ROLE_IDS`, or name matching (`hq`, `Executive Leadership`, `staff`).
*   **Permissions**:
    *   **Full Access**: Implicit read and write (modify) privileges across all forks, Notion databases, meetings, and configurations.
    *   **Bypasses All Scoping**: Automatically passes `isAuthorizedForCity` and `isAuthorizedForForkId` gates.

### 2. Department Leads (Global Track Leads)
*   **Identification**: Holds the `outreach-lead`, `tech-lead`, `creative-lead`, or `ops-lead` roles.
*   **Permissions**:
    *   **Cross-Fork Control**: Treated as Global Admins for execution purposes.
    *   **Full Access**: Bypasses local city checks, allowing view & modification of all fork pages and event structures.

### 3. Parent Track Contributors
*   **Identification**: Holds the `@Contributor` role + a global track role (e.g., `tech`, `ops`, `creative`, `outreach`) but **does not** hold any local `contributor-{city}` role.
*   **Permissions**:
    *   **Cross-Fork VIEW Access**: Authorized to *view* the dashboard, health scores, and metrics of any city fork.
    *   **No Modify Privileges**: Cannot create events, submit reports, or modify fork status.

### 4. Fork Leads
*   **Identification**: Meets Local Fork Member requirements + holds the `Fork Lead` role (or designated as lead in the Notion registry).
*   **Permissions**:
    *   **Full Local Control**: Full read and write (modify) access to any data associated with their specific city fork.
    *   **No Cross-Fork Access**: Cannot view or modify private data from other city forks.

### 5. Local Track Leads (Fork Department Leads)
*   **Identification**: Meets Local Fork Member requirements + holds a track lead role (e.g. `tech-lead` / `Tech Lead`, `creative-lead` / `Creative Lead`, `ops-lead` / `Ops Lead`, `outreach-lead` / `Outreach Lead`).
*   **Permissions**:
    *   **General Local VIEW**: Can view all aspects of their own city fork.
    *   **Track-Restricted Modify**: Can modify fork components and events *only if* the target activity falls within their track (e.g., a `tech-lead` can schedule a technical event or modify a tech report for their fork, but cannot modify creative tasks).

### 6. Fork Contributors
*   **Identification**: Holds `@Contributor` + city role + `contributor-{city}` role.
*   **Permissions**:
    *   **Local VIEW-Only**: Can view all elements of their own city fork.
    *   **No Modify Privileges**: Cannot execute administrative/update commands.

### 7. Fork Community Members
*   **Identification**: Holds the city role (e.g., `delhi`) but **does not** hold the `@Contributor` role.
*   **Permissions**:
    *   **Public Local VIEW**: Can view public channels and resources of their city fork.
    *   **No Private Access**: Cannot view restricted contributor channels or execute bot commands.

---

## 🎙️ Dynamic Meeting Scopes

Meeting recording voice channels use role-scoping variables to dynamically establish permissions:

*   `invite`: Only explicit meeting attendees are granted join permissions.
*   `open`: Any user holding the `@Contributor` or `hq` role can join.
*   `hq`: Restricted solely to members holding the `hq` role.
*   `fork:{city}`: Restricted to members holding the `contributor-{city}` role.
*   `network:{track}`: Restricted to members holding the global track role (e.g., `tech`).
*   `fork:{city}:{track}`: Restricts access to members who hold **both** the city contributor role and the track role.
