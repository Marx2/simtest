# aisim

aisim is a simulation of a city. It simulates the behavior of people in a city, their interactions, movement, and the impact of weather. The simulation is done by using an LLM Ollama Phi4 model to generate events and interactions between sims.

## Installation
Clone repository, enter it and then:

```bash
python -m venv venv
source venv/bin/activate
pip install -r aisim/requirements.txt
```

## Usage

```bash
python -m aisim.src.main
```

## Test - not working yet

```bash
python -m unittest aisim/tests/test_conversation.py
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details