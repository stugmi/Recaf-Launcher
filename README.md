# Recaf Launcher

A simple solution for running Recaf.

## Downloading

- See the ['releases' page](https://github.com/Col-E/Recaf-Launcher/releases)

## Usage

![Screenshot of GUI and CLI](media/preview.png)

For more details see the [Recaf user-guide page on using the launcher as a GUI or CLI](https://recaf.coley.software/user/install/via-launcher.html).

### Python command line interface

A lightweight Python reimplementation of the launcher is available in the
`pylauncher` package. It exposes similar functionality to the Java CLI,
including Java runtime discovery and JavaFX dependency management.

```bash
# Discover installed JDKs
python -m pylauncher.cli detect-java

# Download a compatible JavaFX runtime next to your Recaf installation
python -m pylauncher.cli update-javafx
```

The Python CLI stores JavaFX artefacts in the same directories as the Java
launcher, so you can freely mix and match the tools.

## Additional Information

- [Why does this launcher exist?](https://recaf.coley.software/user/install/why.html)
- [How do I manually run Recaf without this launcher?](https://recaf.coley.software/user/install/via-manual.html)