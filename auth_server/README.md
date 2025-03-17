# Project Title

TEN-Agent Auth Server

## Description

This project is an authentication server for the TEN-Agent system. It handles user authentication and authorization.

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/TEN-Agent-source.git
    ```
2. Navigate to the auth_server directory:
    ```sh
    cd TEN-Agent-source/auth_server
    ```
3. Install the dependencies:
    ```sh
    npm install
    ```

## Usage

1. Start the server:
    ```sh
    npm start
    ```
2. The server will be running at `http://localhost:3000`.

## Environment Variables

Set the following environment variables to specify the paths for the private key and public certificate. If not set, the application will use the default paths within the project directory.

```sh
export PRIVATE_KEY_PATH=./path/to/your/private_key.pem
export PUBLIC_CERT_PATH=./path/to/your/certificate.pem
```

## Sample HTTP curl Commands

### Register a new user
```sh
curl -k 'https://localhost:3000/user/register' \
  -H 'Content-Type: application/json' \
  --data-raw '{"username":"testuser", "hashedPwd":"testpassword"}'
```


## Generate Private Key and Public Certificate

### Create a private key
```sh
mkdir -p ./certs
openssl genpkey -algorithm RSA -out ./certs/private_key.pem -aes256
```

### Create a public certificate
```sh
openssl req -new -x509 -key ./certs/private_key.pem -out ./certs/certificate.pem -days 365
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
