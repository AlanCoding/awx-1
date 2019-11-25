The `requirements.txt` and `requirements_ansible.txt` files are generated from `requirements.in` and `requirements_ansible.in`, respectively, using `pip-tools` `pip-compile`.

## How To Use

Commands should from inside `./requirements` directory of the awx repository.

Make sure you have `patch, awk, python3, python2, python3-venv, python2-virtualenv, pip2, pip3` installed.

### Upgrading or Adding Select Libraries

If you are developing some feature and need to add or upgrade one or a few
libraries to support that feature, then modify `requirements.in` according to
you needs, and then run the script:

`./updater.sh`

### Upgrading Secondary Dependencies

You can also upgrade (`pip-compile --upgrade`) the dependencies by running `./updater.sh upgrade`.
This might be needed if you require a fix from a library which is not explicitly
listed under `requirements.in`.

If you are using the development container image, you need to run `dnf install libpq-devel libcurl-devel`.
These packages are removed in the Dockerfile.

### Upgrading Primary Dependencies

You can upgrade the primary dependencies in `requirements.in` files by running

`./updater.sh ascension`

Those lines marked with a comment starting with `# FIX` will not be upgraded by this method. Fixed items should be things known to be break on upgrade, and have a separate work-item associated with them in order to upgrade or replace dependencies.

You may need `dnf -y install gcc redhat-rpm-config python3-devel`.

## What The Script Does

This script will:

  - Update `requirements.txt` based on `requirements.in`
  - Update/generate `requirements_ansible.txt` based on `requirements_ansible.in`
    - including an automated patch that adds `python_version < "3"` for Python 2 backward compatibility
  - Removes the `docutils` dependency line from `requirements.txt` and `requirements_ansible.txt`


## Licenses and Source Files

If any library has a change to its license with the upgrade, then the license for that library
inside of `docs/licenses` needs to be updated.

For libraries that have source distribution requirements (LGPL as an example),
a tarball of the library is kept along with the license.
To download the PyPI tarball, you can run this command:

```
pip download <pypi library name> -d docs/licenses/ --no-binary :all: --no-deps
```

Make sure to delete the old tarball if it is an upgrade.
