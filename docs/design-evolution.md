# Design evolution: v0.1–v0.7

[日本語・詳細版](design-evolution.ja.md) · [Original design notes](history/README.md)

This is a narrative of the design questions rather than a reconstructed Git commit history. The seven prototypes were developed before the first public repository. We preserve the working v0.7 code and the original notes, not invent seven historical commits. The objective is to make local observation and analysis accessible. AFP is a learning and experimental protocol, not a technology that every deployment must use.

| Version | Research question | Decision and result | Tests |
| --- | --- | --- | ---: |
| v0.1 | What is the minimum packet and relay mechanism? | Binary DATA/ACK, TTL, duplicate suppression, radius-based deterministic medium. Demonstrates collision and half duplex, not real hardware. | 3 |
| v0.2 | How should a protocol see a UART radio? | Separate the radio interface, approximate host UART, addressing, queues and RF behavior; add five scenarios and Network Observatory. | 15 |
| v0.3 | Is the simulated node using knowledge unavailable to a physical node? | Independent node clocks, local plans and local recorders, separate field truth, explicit observation window; offline collector preserves missing and unsynchronized data. | 30 |
| v0.4 | Can terrain make two equal-distance links behave differently? | GSI DEM, local projection, Fresnel clearance, dominant knife-edge and frozen profiles. Terrain is an environment input, not host knowledge. Add synthetic-hill comparison. | 43 |
| v0.5 | Can non-specialists plan candidate placements visually? | Loopback Map Planner: configure nodes on a map, save/load JSON, run paired experiments without changing the protocol. | 53 |
| v0.6 | Can the platform work beyond Akeno? | Separate field configuration, map viewport, local origin and base. Provider interfaces; only GSI implemented. | 63 |
| v0.7 | Can we see coverage before choosing receiver locations? | Reuse the exact link model across a circular grid, with clickable profiles and cached provenance. No simulated AFP nodes needed for coverage. | 74 |

## Architecture through the seven prototypes

Blue outlines highlight the principal new or changed responsibilities at each step. Default-colored elements are retained responsibilities. Arrows show logical data or control relationships, not physical wiring or every RF link. These are explanatory diagrams of the historical implementations, not newly reconstructed Git commits.

### v0.1 — Minimal packet and virtual medium

```mermaid
flowchart TD
    C["Shared event clock"] -.-> M["Virtual Medium: radius / collisions"]
    subgraph N["AFP nodes"]
        A["N1: sender"]
        B["N2: relay"]
        D["N3: receiver"]
    end
    A <--> M
    B <--> M
    D <--> M
    C -.-> N
    M --> L["Medium event log"]
    class A,B,D,C,M,L added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*Minimal protocol and shared virtual field. Nodes call the medium directly.*

### v0.2 — Radio abstraction

```mermaid
flowchart TD
    S["Scenario JSON"] --> E["Shared scenario engine"]
    E --> A["AFP Node 1"]
    E --> B["AFP Node 2: relay"]
    E --> D["AFP Node 3"]
    A <--> I1["RadioInterface"]
    B <--> I2["RadioInterface"]
    D <--> I3["RadioInterface"]
    I1 <--> R1["Virtual E220"]
    I2 <--> R2["Virtual E220"]
    I3 <--> R3["Virtual E220"]
    R1 <--> F["Virtual Field: radius / channel / collisions"]
    R2 <--> F
    R3 <--> F
    F --> L["Shared event log"]
    L --> O["Network Observatory"]
    class I1,I2,I3,R1,R2,R3,S,E,O added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*The radio boundary is introduced. UART, queue and RF behavior sit below the protocol; the field log is still centralized.*

### v0.3 — Independent node views and records

```mermaid
flowchart TD
    S["Scenario JSON"] --> E["Split local plans / environment"]
    E --> P1["Local plan 1"]
    E --> P2["Local plan 2"]
    subgraph N1["Node 1"]
        A1["NodeSession / AFPNode"]
        C1["NodeClock 1"] -.-> A1
        A1 <--> R1["RadioInterface / Virtual E220"]
        A1 --> L1["Local Recorder 1"]
        R1 --> L1
    end
    subgraph N2["Node 2 (repeat for N3...)"]
        A2["NodeSession / AFPNode"]
        C2["NodeClock 2"] -.-> A2
        A2 <--> R2["RadioInterface / Virtual E220"]
        A2 --> L2["Local Recorder 2"]
        R2 --> L2
    end
    P1 --> A1
    P2 --> A2
    R1 <--> F["Virtual Field: simulation truth"]
    R2 <--> F
    E --> F
    F --> LF["Field Recorder"]
    L1 --> T["Manifest + JSONL streams"]
    L2 --> T
    LF --> T
    T --> K["Offline Collector"] --> O["Network Observatory"]
    class E,P1,P2,C1,C2,L1,L2,LF,T,K added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*Each node has its own view and clock. Field-only truth goes to the observation side, not the protocol. Two representative nodes are shown.*

### v0.4 — Terrain-aware field

```mermaid
flowchart TD
    G["Geographic config: locations / heights"] --> T["Terrain preparation: FSPL / diffraction"]
    D["GSI elevation tiles / cache"] --> T
    T --> S["Frozen scenario: link profiles / hashes"]
    S --> E["Split local plans / environment"]
    E --> A["AFP Node 1 + local clock"]
    E --> B["AFP Node 2 + local clock"]
    E --> F["Virtual Field: predicted link thresholds"]
    A <--> R1["RadioInterface / Virtual E220"]
    B <--> R2["RadioInterface / Virtual E220"]
    R1 <--> F
    R2 <--> F
    A --> L1["Local Recorder 1"]
    R1 --> L1
    B --> L2["Local Recorder 2"]
    R2 --> L2
    F --> LF["Field Recorder"]
    L1 --> K["Offline Collector"]
    L2 --> K
    LF --> K
    K --> O["Network Observatory"]
    class G,T,D,S,F added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*Terrain changes the field model, not the AFP node. The node never receives a global propagation table.*

### v0.5 — Visual scenario planning

```mermaid
flowchart TD
    U["Operator: place nodes visually"] --> P["Map Planner"]
    M["GSI map tiles"] --> P
    P <--> G["Editable geographic JSON"]
    G --> T["Terrain preparation"]
    D["GSI DEM / cache"] --> T
    T --> S["Frozen scenario"]
    S --> E["Experiment runner"]
    E --> A["AFP nodes / RadioInterface"]
    E --> F["Virtual Field"]
    A <--> F
    A --> L["Local Recorder per node"]
    F --> LF["Field Recorder"]
    L --> K["Offline Collector"]
    LF --> K
    K --> O["Network Observatory"]
    class U,P,M,G added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*The planner is a new way to construct scenarios, not a new radio protocol. Existing simulation and observation remain intact.*

### v0.6 — Field configuration and providers

```mermaid
flowchart TD
    CAT["Default catalog: Akeno sample"] --> G["Field Config"]
    X["Other region JSON"] --> G
    G <--> P["Map Planner"]
    G --> V["Viewport (not terrain origin or base)"]
    G --> T["Terrain preparation"]
    V --> P
    MP["Map Provider: GSI"] --> P
    DP["ElevationProvider"] --> T
    D["GSI DEM adapter / cache"] --> DP
    T --> S["Frozen scenario"]
    S --> E["Experiment runner"]
    E --> A["AFP nodes / RadioInterface"]
    E --> F["Virtual Field"]
    A <--> F
    A --> L["Separate local / field records"]
    F --> L
    L --> K["Offline Collector"] --> O["Network Observatory"]
    class CAT,X,G,V,MP,DP added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*Akeno becomes a selectable data configuration. Map and elevation providers are separate; only GSI is implemented.*

### v0.7 — Single-source coverage prediction

```mermaid
flowchart TD
    G["Field Config"] <--> P["Map Planner"]
    MP["Map Provider"] --> P
    P --> T["Pairwise terrain preparation"]
    P --> C["Coverage Engine: one base + grid"]
    T --> M["Shared path model"]
    C --> M
    D["ElevationProvider / DEM cache"] --> M
    T --> S["Frozen scenario"]
    S --> E["Experiment runner"]
    E --> A["AFP nodes / RadioInterface"]
    E --> F["Virtual Field"]
    A <--> F
    A --> R["Separate local / field records"]
    F --> R
    R --> K["Offline Collector"] --> O["Network Observatory"]
    C --> J["Coverage JSON / map overlay"]
    J --> P
    class C,M,J added
    classDef added fill:#E0F2FE,stroke:#0369A1,color:#0C4A6E,stroke-width:2px
```

*The coverage branch bypasses the packet engine. Both branches use the same physics; grid points are not AFP nodes.*

## Important architectural decisions

- **A radio request is not an RF delivery.** The host admission result, UART completion, hidden module behavior and end-to-end ACK are distinct.
- **No simulation oracle in the host.** The radio callback supplies bytes and optional RSSI. Field-only identities and causes of RF failure remain on the observation side.
- **Records are independent of the simulator.** Local clocks, streams and a manifest can be collected offline. A missing stream is not evidence of a lost packet. A simulated exact clock mapping is not a physical synchronization method.
- **The radio model is independent of AFP.** A prepared terrain scenario freezes the predictions. A coverage grid uses the same path model but no packet engine.
- **Akeno is a field, not a software dependency.** The local coordinate origin is not the source node or map viewport. Geography is configuration; provider adapters may be added when needed.
- **Preserve evidence rather than manufacture certainty.** The final baseline passes 74 automated tests and the eight prior scenario summaries. A Windows GSI-backed coverage run completed 1,961 cells. This verifies operation, not the radio propagation accuracy. See [validation](validation.md).

## From virtual experiments to physical research

Protocol Research studies delivery under controlled conditions. Radio Field Research studies location, propagation and empirical residuals. Field Engineering studies antennas, weatherproofing, sensors, power, installation and maintenance. We intend to use real devices to test all three in the Akeno field. No embedded firmware has been delivered yet.

Meshtastic and LoRaWAN are useful reference systems, not competitors to defeat. If an existing implementation satisfies the observation requirements, use it. If a gap appears, document a testable question, compare with the reference and justify the smallest useful change. Building a prototype for learning is valid; deploying it merely because it was built is not.
