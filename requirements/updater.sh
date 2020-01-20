#!/bin/sh
set -ue

requirements_in="$(readlink -f ./requirements.in)"
requirements_ansible_in="$(readlink -f ./requirements_ansible.in)"
requirements_setup_in="$(readlink -f ./requirements_setup_requires.in)"

requirements="$(readlink -f ./requirements.txt)"
requirements_ansible="$(readlink -f ./requirements_ansible.txt)"
requirements_setup="$(readlink -f ./requirements_setup_requires.txt)"

pip_compile="pip-compile --no-header --quiet -r --allow-unsafe"

check_prerequisites() {
  for thing in patch awk python3 python2 virtualenv ; do
      command -v $thing >/dev/null 2>&1 || { echo "$thing not installed or available. Please fix this before running." ; exit 1 ; }
  done
}

_cleanup() {
  cd /
  test "${KEEP_TMP:-0}" = 1 || rm -rf "${_tmp}"
}

install_deps() {
  pip install pip --upgrade
  pip install pip-tools
}

generate_requirements_v3() {
  venv="./venv3"
  python3 -m venv "${venv}"
  # shellcheck disable=SC1090
  . "${venv}/bin/activate"

  install_deps

  ${pip_compile} --output-file "$2" "$1"
}

generate_requirements_v2() {
  venv="./venv2"
  virtualenv -p python2 "${venv}"
  # shellcheck disable=SC1090
  PS1="" . "${venv}/bin/activate"

  install_deps

  ${pip_compile} --output-file "$2" "$1"
}

generate_patch() {
  a="$2"
  b="$1"
  replace='; python_version < "3" #'

  # most elegant/quick solution I could come up for now
  out="$(diff --ignore-matching-lines='^#' --unified "${a}" "${b}" | \
    awk -v replace="${replace}" '{ if (/^+\w/){ $2=replace; print;} else print; }' | \
    sed 's/ ;/;/g')"
  test -n "${out}"
  echo "${out}"
}

main() {
  check_prerequisites

  _tmp="$(mktemp -d --suffix .awx-requirements XXXX -p /tmp)"
  trap _cleanup INT TERM EXIT

  if [ "$1" = "upgrade" ]; then
      pip_compile="${pip_compile} --upgrade"
  fi

  cp -vf requirements.txt requirements_ansible.txt "${_tmp}"
  cp -vf requirements_ansible.txt "${_tmp}/requirements_ansible_py3.txt"

  echo "Working temporary directory ${_tmp}"
  cd "${_tmp}"

  generate_requirements_v3 ${requirements_ansible_in} requirements.txt

  generate_requirements_v3 ${requirements_ansible_in} requirements_ansible_py3.txt
  generate_requirements_v2 ${requirements_ansible_in} requirements_ansible.txt

  generate_requirements_v3 ${requirements_setup_in} requirements_setup_requires_py3.txt
  generate_requirements_v2 ${requirements_setup_in} requirements_setup_requires.txt

  sed -i 's/^docutils.*//g' requirements.txt

  generate_patch requirements_ansible.txt requirements_ansible_py3.txt | patch -p4 requirements_ansible_py3.txt
  generate_patch requirements_setup_requires.txt requirements_setup_requires_py3.txt | patch -p4 requirements_setup_requires_py3.txt

  cp -vf requirements_ansible_py3.txt "${requirements_ansible}"
  cp -vf requirements_setup_requires_py3.txt "${requirements_setup}"
  cp -vf requirements.txt "${requirements}"

  _cleanup
}

# set EVAL=1 in case you want to source this script
test "${EVAL:-0}" = "1" || main "${1:-}"
