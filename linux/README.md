# Linux Development

## Environment setup

To be able to setup a complete development environment, you'll need to manually
install some system libraries (including the development version of your
distribution corresponding packages):
- log / notifications support: `libdbus` is needed.
- Uinput support: `libxkbcommon` is needed by the [`xkbcommon` package](https://pypi.org/project/xkbcommon)

For the rest of the steps, follow the [developer guide](../doc/developer_guide.md).
