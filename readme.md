#Para preparar o ambiente
pip install -r requirements.txt
pip download -r requirements.txt --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp --abi cp39 --only-binary=:all: -d packages
pip install --no-index --find-links=packages -r requirements.txt

#Para iniciar o projeto
python -m uvicorn app:app --reload
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000





