Lmod config for VUB-HPC
=======================

This repo contains the files for tweaking Lmod for [VUB-HPC](https://hpc.vub.be).

- Some extra strings for the language file used in our `SitePackage.lua`
- Our `SitePackage.lua`, see below what it all does
- Script to generate the Lmod cache on our systems
- `admin.list` file to give nag message on some modules

All of these get installed in `/etc/lmod` where recent versions of Lmod will
pick them up.

# SitePackage

The `SitePackage.lua` contains a couple of hooks:
- `logmsg`: A general function for logging
- `module_age`: calculates the 'age' of a module using the toolchain version
- `load_hook`: logging of loaded modules (and loaded by user or as dependency).
  It will also give warnings for 'old' modules.
- `startup_hook`: logs how Lmod was called and the used arguments
- `msg_hook`: adds a custom message to avail/list/spider
- `errwarnmsg_hook`: add as general disclaimer to all warnings and errors.
  It also tweaks the message on specific errors.
- `visible_hook`: hides some modules by name pattern or age
- `get_avail_memory`: returns the (cgroup) memory limit inside the current
  environment. This is added to the module sandbox to set memory limits
  depending on the allocated resources.
