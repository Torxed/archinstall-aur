# archinstall-aur
Archinstall plugin concept to handle AUR packages.<br>

⚠️ There is no support offered for AUR packages, but if you have questions about this or other plugins, or surrounding archinstall - ping me on the archinstall discord server and we can bounce ideas.

---

🚨 Important: This is not something that will ever be shipped with archinstall or the archinstall guided installer. This repo serves as an example to show how plugins can be created to enrich archinstall with external functions that experienced users can optionally install and optionally use.

# Usage

Either put it as a parameter via `archinstall --plugin https://raw.githubusercontent.com/Torxed/archinstall-aur/main/archinstall_aur/__init__.py`.
After which you can add AUR packages to the `"Additional packages"` question in the menu.

Or via a `--conf` file:
```json
{
    "plugin" : "https://raw.githubusercontent.com/Torxed/archinstall-aur/main/archinstall_aur/__init__.py",
    "packages" : [
        "nano",
        "wget",
        "yay-bin"
    ]
}
```
