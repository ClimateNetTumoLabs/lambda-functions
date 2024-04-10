python3 -m venv venv
source venv/bin/activate

PYTHON_VERSION=$(ls ./venv/lib | grep python)
export PYTHON_VERSION
pip install -r requirements.txt

deactivate
cd venv/lib/"$PYTHON_VERSION"/site-packages || exit
zip -r9 "${OLDPWD}"/lambda_function.zip .
cd "$OLDPWD" || exit
zip -g lambda_function.zip lambda_function.py
zip -g lambda_function.zip config.py
