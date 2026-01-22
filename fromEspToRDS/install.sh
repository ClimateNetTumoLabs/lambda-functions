rm -f lambda_function.zip
rm -rf venv

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip

# IMPORTANT: force Linux + Python 3.10 wheel download (no compiling)
pip install -r requirements.txt \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 313 \
  --only-binary=:all: \
  --upgrade \
  --target package

deactivate

# remove macOS pycache files if any
find package -type d -name "__pycache__" -exec rm -rf {} +
find package -type f -name "*.pyc" -delete

cp lambda_function.py package/
cp config.py package/

cd package
zip -r9 ../lambda_function.zip .
cd ..
