#!/usr/bin/env bash
#encoding=utf8

function check_installed_pip() {
   ${PYTHON} -m pip > /dev/null
   if [ $? -ne 0 ]; then
        echo "-----------------------------"
        echo "Installing Pip for ${PYTHON}"
        echo "-----------------------------"
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        ${PYTHON} get-pip.py
        rm get-pip.py
   fi
}

# Check which python version is installed
function check_installed_python() {
    if [ -n "${VIRTUAL_ENV}" ]; then
        echo "Please deactivate your virtual environment before running setup.sh."
        echo "You can do this by running 'deactivate'."
        exit 2
    fi

    for v in 9 8 7
    do
        PYTHON="python3.${v}"
        which $PYTHON
        if [ $? -eq 0 ]; then
            echo "using ${PYTHON}"
            check_installed_pip
            return
        fi
    done 

    echo "No usable python found. Please make sure to have python3.7 or newer installed"
    exit 1
}

function updateenv() {
    echo "-------------------------"
    echo "Updating your virtual env"
    echo "-------------------------"
    if [ ! -f .env/bin/activate ]; then
        echo "Something went wrong, no virtual environment found."
        exit 1
    fi
    source .env/bin/activate
    SYS_ARCH=$(uname -m)
    echo "pip install in-progress. Please wait..."
    ${PYTHON} -m pip install --upgrade pip
    REQUIREMENTS=requirements.txt
    if [ "${SYS_ARCH}" == "armv7l" ]; then
        echo "Detected Raspberry, installing cython."
        ${PYTHON} -m pip install --upgrade cython
    fi

    ${PYTHON} -m pip install --upgrade -r ${REQUIREMENTS}
    if [ $? -ne 0 ]; then
        echo "Failed installing dependencies"
        exit 1
    fi
    ${PYTHON} -m pip install -e .
    if [ $? -ne 0 ]; then
        echo "Failed installing 3commas-cyber-bots"
        exit 1
    fi
    echo "pip install completed"
    echo
}

function install_mac_newer_python_dependencies() {    
    
    if [ ! $(brew --prefix --installed hdf5 2>/dev/null) ]
    then
        echo "-------------------------"
        echo "Installing hdf5"
        echo "-------------------------"
        brew install hdf5
    fi

    if [ ! $(brew --prefix --installed c-blosc 2>/dev/null) ]
    then
        echo "-------------------------"
        echo "Installing c-blosc"
        echo "-------------------------"
        brew install c-blosc
    fi    
}

# Install bot MacOS
function install_macos() {
    if [ ! -x "$(command -v brew)" ]
    then
        echo "-------------------------"
        echo "Installing Brew"
        echo "-------------------------"
        /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    fi
    #Gets number after decimal in python version
    version=$(egrep -o 3.\[0-9\]+ <<< $PYTHON | sed 's/3.//g')
    
    if [[ $version -ge 9 ]]; then               #Checks if python version >= 3.9
        install_mac_newer_python_dependencies
    fi
    install_talib
}

# Install bot Debian_ubuntu
function install_debian() {
    sudo apt-get update
    sudo apt-get install -y git $(echo lib${PYTHON}-dev ${PYTHON}-venv)
}

# Upgrade the bot
function update() {
    git pull
    updateenv
}

# Reset Develop or Stable branch
function reset() {
    echo "----------------------------"
    echo "Resetting virtual env"
    echo "----------------------------"

    if [ -d ".env" ]; then
        echo "- Deleting your previous virtual env"
        rm -rf .env
    fi
    echo
    ${PYTHON} -m venv .env
    if [ $? -ne 0 ]; then
        echo "Could not create virtual environment. Leaving now"
        exit 1
    fi
    updateenv
}

function install() {
    echo "---------------------------------"
    echo "Installing mandatory dependencies"
    echo "---------------------------------"

    if [ "$(uname -s)" == "Darwin" ]
    then
        echo "macOS detected. Setup for this system in-progress"
        install_macos
    elif [ -x "$(command -v apt-get)" ]
    then
        echo "Debian/Ubuntu detected. Setup for this system in-progress"
        install_debian
    else
        echo "This script does not support your OS."
        echo "If you have Python3.6 or Python3.7, pip, virtualenv you can continue."
        echo "Wait 10 seconds to continue the next install steps or use ctrl+c to interrupt this shell."
        sleep 10
    fi
    reset
    echo "-----------------------------------------"
    echo "Installation of 3commas-cyber-bots done!"
    echo "-----------------------------------------"
    echo "You can now enter the virtual environment by executing 'source .env/bin/activate'."
    echo
    if [ ! -f "config.py" ]; then
        echo "-----------------------------------------"
        echo "Creating config file from example config."
        echo "-----------------------------------------"
        cp example.config.py config.py
        echo "Edit 'config.py' to include your API keys and bot preferences."
        echo
    fi
    echo
    echo "Run the 'galaxyscore.py' or 'altrank.py' script file to start the bot manually."
    echo "Or install the services file for automated starts."
}


function help() {
    echo "usage:"
    echo "	-i,--install    Install 3commas-cyber-bots from scratch"
    echo "	-u,--update     Command git pull to update."
}

# Verify if 3.7 or 3.8 is installed
check_installed_python

case $* in
--install|-i)
install
;;
--update|-u)
update
;;
*)
help
;;
esac
exit 0
