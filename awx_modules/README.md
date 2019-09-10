# AWX Ansible Modules

These modules allow for easy interaction with an AWX or Ansible Tower server
in Ansible playbooks.

The previous home for these modules was in https://github.com/ansible/ansible
inside the folder `lib/ansible/modules/web_infrastructure/ansible_tower`.

## Tests

Tests to verify compatibility with the most recent AWX code are being
built in `awx_modules/test/awx`. These tests require that all of the
following are available in the python environment:

 - AWX
 - Ansible
 - tower-cli

This requires a non-obvious configuration, and a special install location
is used for it. In the AWX development container, you can run the
targets:

```
make prepare_modules_venv
make test_modules
```

Subsequently, you can run just `make test_modules`.

## Building

To build, you should not be in the AWX virtual environment.
This should work on any machine that has a sufficiently recent version
of Ansible installed.

```
cd awx_modules
ansible-galaxy build
```

This will leave a tar file in the awx_modules directory.
