#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

pipenv run alembic upgrade head
pipenv run python main.py