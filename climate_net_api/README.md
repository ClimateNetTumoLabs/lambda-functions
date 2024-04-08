# Set Up and Run Lambda Function to Read Data from the AWS RDS

## This README file provides instructions on set up and run a Lambda function that read data from the RDS database and respond.
## Folder Contents

* `config.py`: File containing configuration data such as AWS RDS endpoint, master username, master password, and database name.
* `lambda_function.py`: Lambda function code that read data from the RDS database.
* `requirements.txt`: List of Python dependencies for the Lambda function.
* `install.sh`: Script to create a zip file containing the function code and dependencies ready for uploading to AWS Lambda.


## Setup and Execution Steps
1. **Configure the Configuration Data**

    - Duplicate [config.py.template](config.py.template) in the same directory and rename it to [config.py](config.py)

    - In the `config.py` file, fill the corresponding credentials

2. **Create and Package the Lambda Function**

    Run the `install.sh` script to create a zip file ready for upload to AWS Lambda:
    
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    This command will create a file named `lambda_function.zip` in the folder with your files.
