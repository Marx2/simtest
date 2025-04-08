# aisim

aisim is a simulation of a city. It simulates the behavior of people in a city, their interactions, movement, and the impact of weather. The simulation is done by using an LLM Ollama Phi4 model to generate events and interactions between sims.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
cd simtest
conda activate aisim && conda run -n aisim python -m aisim.src.main
```

## Test

```bash
python -m unittest aisim/tests/test_conversation.py
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details