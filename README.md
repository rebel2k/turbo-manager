# Turbo-manager

## Prepare the environment

This is a Python program, so it needs Python to run. If you don't have Python install it first.

You also need pipenv to have a virtual environment to run it easily. If you don't have pipenv yet, just install pipenv using the following command:

MacOS: `brew install pipenv`
Other systems: `pip install --user pipenv`

Then, install the dependancies:
`pipenv install -r requirements.txt`
Enter the newly created virtual environment
`pipenv shell`

## Run the program

`streamlit run Home.py`

## Tips for VScode

To figure out the virtutal environment, run `pipenv --py`
Then, with the VScode palette, picks "Python: chose environment" and pick up the one you found with the previous command.
