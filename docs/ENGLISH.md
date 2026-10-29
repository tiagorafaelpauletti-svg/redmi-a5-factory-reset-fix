# Redmi A5: factory reset blocked during `set_policy_failed:/data/per_boot`

This repository documents two Redmi A5 recoveries completed on October 29, 2026. Both devices booted into Recovery with `NEED TO WIPE USERDATA`, but factory reset failed. Both used `serenity`, Android 15 Go build `A15.0.13.0.VGWMIXM`, eMMC, active slot A and a locked bootloader.

## Confirmed finding

The 128 MiB ext4 `rescue` partition is mounted as `/cache` by Recovery. Its file `recovery/last_extension_parameters` contained:

```text
disable_factoryreset=1
```

Recovery logs showed the file being loaded, followed by `config.disable_format=1` and `WipeData disable_format is true`. This explains why resetting was blocked. It does **not** identify the original cause of the `/data/per_boot` failure or who set the parameter.

For each device we dumped its own `rescue`, resolved this file through ext4 directories and extents, and changed **one byte**, `1` to `0`. We wrote that device-specific image back to `rescue`, read the full partition back and matched SHA-256. After `reboot-recovery`, the built-in factory reset completed. The operator confirmed Android booted on both devices.

The file had different physical offsets in the two images. **Never use a fixed offset or another phone's partition image.**

## Scope and risks

Factory reset erases user data. BROM access runs third-party code; interrupted or incorrect writes may require service recovery. Only work on a device you own or administer with permission. If the reset restriction is an intentional management policy, coordinate with its administrator. This project does not remove Google accounts, FRP or enterprise enrollment.

No permanent bootloader unlock, root, firmware replacement or `persist`/calibration erasure was required. Two same-build devices are limited evidence, not universal compatibility.

## Offline utility

`rescue_config.py` uses the Python standard library and **never accesses USB or flashes anything**. It supports the narrowly tested 128 MiB ext4 profile, resolves the configuration by pathname, checks an independently extracted reference and writes a new image. It refuses unsupported features, dirty filesystems, pending journal replay, metadata checksums, complex extents, unexpected content and output overwrites.

```text
python rescue_config.py inspect private/rescue-original.img
python rescue_config.py patch private/rescue-original.img --reference-file private/extracted/recovery/last_extension_parameters --output private/rescue-patched.img
python rescue_config.py verify private/rescue-patched.img private/rescue-readback.img
python -m unittest discover -s tests -v
```

The full [technical procedure in Portuguese](PROCEDIMENTO.md) explains obtaining a private dump, WinUSB driver selection, manual writing, full readback verification and original-image recovery. Understand it before issuing any device command. There is no automatic flasher in this repository.

## Access method and upstream attribution

BROM access used [TomKing062's CVE-2022-38694 project](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader), its UMS9230**E** / Tecno KL4 loaders, and the libusb Windows build of [spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash). The generic UMS9230 package is not interchangeable. Do not run the full automated unlock batch: that is a different operation involving bootloader/SPL writes.

[Upstream issue 327](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader/issues/327) documents A5 access; [issue 262](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader/issues/262) also documents a failed unlock and recovery. These are context, not proof every device is compatible.

The old 2015 SPRD driver failed Windows signature enforcement with code 52. The working path used [Zadig](https://zadig.akeo.ie/) and WinUSB for **VID `1782`, PID `4D00`**, without disabling Windows signature checks. Use the supplied device preset and verify the ID to avoid replacing an unrelated USB driver. A blank phone screen alone does not confirm BROM access.

No dumps, complete logs, serial numbers, IMEIs, firmware, drivers or exploit binaries are published here. Obtain external tools from their original maintainers and respect their licenses. Original code/documentation: MIT; practical recovery and validation by Tiago Rafael with Codex assistance.
