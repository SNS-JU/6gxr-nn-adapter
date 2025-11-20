# North Node Adapter (NNA)

## Installation

NNA requires [Python](https://www.python.org/) to run. The NNA application has been developed and tested with Python version 3.12.3.

First, set up a Python virtual environment (use Python version 3.12.3) for the NNA application. You can use [Anaconda](https://www.anaconda.com/), [venv](https://docs.python.org/3/tutorial/venv.html), [pyenv](https://github.com/pyenv/pyenv), or whatever you prefer.

Once you have a Python virtual environment running for NNA, install all required Python packages by invoking the following in the NNA project's root directory:

```sh
$ python3 -m pip install -r requirements.txt
```

That's it. You are ready to run the NNA application.

## Running the NNA application

To run the NNA application, invoke the following command in the NNA project's root directory. This command starts the NNA application (starts listening for REST requests on port 5000).

```sh
$ python3 src/nna.py
```

If you want to run the NNA application under a production environment with a WSGI server, you can use [Waitress](https://pypi.org/project/waitress/). To run under Waitress, invoke the following in the NNA project's root directory:

```sh
$ cd src/
$ waitress-serve --listen=*:5000 nna:app
```

## Docker

The NNA application is easy to install and deploy in a Docker container.

By default, the Docker will expose port 5000, so change this within the Docker configuration files if necessary. When ready, simply use the Docker Compose to build the image and start the container.

```sh
$ docker compose build
$ docker compose up
```

To clean up, press Ctrl + C and invoke the following:

```sh
$ docker compose down
```
