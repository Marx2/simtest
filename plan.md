# AI Sims Simulation - Project Plan

## Overview

A single-player 2D life simulation game where AI-driven Sims live autonomously in a dynamic city. Sims perform daily activities, interact with each other, and respond to weather conditions, relationships, and memories. The simulation is scalable, supporting adjustable population size, city expansion, and time control. Sims use local AI models (Ollama) for conversations and decision-making.

## Features

1.  **City Simulation & Movement**

    *   2D city layout with streets, buildings, workplaces, and public areas.
    *   Sims navigate using pathfinding algorithms (A* or Dijkstra’s algorithm).
    *   Daily routines: work, leisure, home activities.
    *   Scalability: Small towns → Large cities.

2.  **AI-Powered Sims (Generative Agents)**

    *   Memory-based decision-making (past experiences, **long-term goals, and personality traits** influence behavior).
    *   Local AI (Ollama) generates conversations and thoughts.
    *   Sims form friendships, rivalries, **family ties, and romantic interests** dynamically.
    *   Mood system affects interactions and daily choices.

3.  **Social Dynamics & Relationships**

    *   Friendship & Reputation System: Sims remember past interactions.
    *   Gossip & Rumors: Reputation spreads within social circles.
    *   Personality Traits: Each Sim has unique behavior (shy, outgoing, aggressive, etc.).
    *   Group Interactions: Sims form social groups and attend events.

4.  **Weather System**

    *   Dynamic Weather: Sunny, Rainy, Snowy, Cloudy.
    *   Impact on Sims:
        *   Rain makes Sims use umbrellas or stay indoors.
        *   Heatwaves encourage seeking shade or drinking cold beverages.
        *   Snow slows movement and encourages indoor activities.
    *   Weather Animation & Transitions

5.  **UI & Simulation Controls**

    *   Time Controls: Pause, Play, Fast-Forward (2x, 4x, 10x speed).
    *   Adjustable Settings:
        *   Weather Intensity
        *   Population Size
        *   AI Behavior Tuning (Social Interaction Frequency, Personality Diversity)
    *   Data Visualization & Analytics:
        *   Graphs & Charts:
            *   **Happiness Trends**
            *   **Social Network Map**
    *   Event Logs: Displays major events & memory-based decisions.

6.  **Scalability & Performance**

    *   Adjustable number of Sims (from small neighborhoods to large-scale cities).
    *   Procedural city expansion to support growing populations.
    *   Multithreading & Optimization:
        *   Sims run in parallel for large-scale simulation.
        *   AI processing (Ollama) handled asynchronously.

7. **Graphics**

    *   Inspired by "generative\_agents" project.
    *   2D sprites for Sims and environment.
    *   Simple animations for actions and weather effects.
    *   Clear visual representation of relationships (e.g., color-coded connections on the social network map).
    *   Example:

        ```mermaid
        graph LR
            A[Sim 1] --> B(Sim 2)
            A --> C{Sim 3}
            B --> D([Sim 4])
            C --> D
            style A fill:#f9f,stroke:#333,stroke-width:2px
            style B fill:#ccf,stroke:#333,stroke-width:2px
            style C fill:#fcc,stroke:#333,stroke-width:2px
            style D fill:#cff,stroke:#333,stroke-width:2px
        ```

## Tech Stack

*   Language: Python (Conda virtual environment)
*   Graphics Engine: Pygame
*   AI Models: Ollama (local execution)
*   Pathfinding: NetworkX, A* Algorithm
*   Data Visualization: Matplotlib
*   Multithreading: Python threading for large-scale Sims

## Development Plan

1.  Phase 1: Core Simulation Framework
2.  Phase 2: AI Sims & Social System
3.  Phase 3: UI & Control Features
4.  Phase 4: Scalability & Optimization

## Final Notes

*   No multiplayer or modding (pure single-player simulation).
*   Focus on realistic AI behavior & emergent storytelling.
*   The game should run efficiently even with hundreds of Sims in a large city.

## Next Steps

*   Set up the project structure & initial Conda environment.
*   Implement core simulation with Sims, movement, and weather.
*   Expand AI interactions, relationships, and social dynamics.
*   Develop UI controls & data visualization features.
*   Optimize for large-scale simulations.
