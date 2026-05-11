# Fusion Script Generator

AI-powered parametric CAD script generation for Autodesk Fusion 360.

This tool interviews you about a part you want to 3D model, then generates a parametric Python script that builds it directly in Fusion 360. It handles the "gotchas" of the Fusion API and ensures your designs are ready to run.

## Features

- **Natural Language Interview**: No need to know CAD terminology. Describe what you want to build, and the tool will ask the right questions to define the geometry.
- **Parametric Output**: All dimensions are pulled into a parameters block at the top of the script for easy tweaking.
- **Automatic Organization**: Scripts are saved in the correct folder structure required by Fusion 360.
- **Robust API Usage**: Uses proven patterns for coordinate transforms, profile selection, and reliable geometric operations.

## How It Works

1.  **Interview**: The tool asks about the purpose, shape, critical dimensions, and features of your part.
2.  **Planning**: A geometric decomposition plan is created and verified with you.
3.  **Generation**: A Python script is generated using the Fusion 360 API.
4.  **Handoff**: The script is saved to your configured Fusion scripts folder.
5.  **Iteration**: Tweak dimensions by editing the parameters in the generated script or asking the tool for modifications.

## Configuration

The tool is configured to write scripts to:
`~/FusionScripts/`

Each script is placed in a subfolder of the same name to comply with Fusion 360's loading requirements.

## Getting Started

To use this as a skill, ensure the `SKILL.md` is registered with your AI assistant.
