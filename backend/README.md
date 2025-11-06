# Sparkth Backend

Sparkth is a free, open source, extensible, science-driven, AI-first learning platform. It is under active development by [Edly](https://edly.io/).

This repository is organized as a [Cargo workspace](https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html) with two main components:

- `app_core/`: a library crate for database access (PostgreSQL via Diesel)
- `web_api/`: a binary crate that serves HTTP APIs

## Prerequisites

Before building or running the project, make sure you have the following installed:

- Rust ([documentation](https://doc.rust-lang.org/book/ch01-01-installation.html)):
    
        curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh

- [PostgreSQL](https://www.postgresql.org/) (local or remote)
- [libpq](https://www.postgresql.org/docs/current/libpq.html) (PostgreSQL client library, required by Diesel)
- [diesel_cli](https://diesel.rs/guides/getting-started#installing-diesel-cli)

    You can use this to install `diesel_cli` with only PostgreSQL:
        
        cargo install diesel_cli --no-default-features --features postgres

    > If you encounter linker errors related to `-lpq`:
    >       
    >       note: ld: library not found for -lpq
    >           clang: error: linker command failed with exit code 1 (use -v to see invocation)
    >
    > Install and link `libpq` using:
    >
    >       brew install libpq
    >       brew link --force libpq

## Setup Instructions

### 1. Clone the repository:

Checkout the code:

    git clone git@github.com:edly-io/sparkth_backend.git
    cd sparkth_backend

### 2. Create a `.env` file

    cp .env.example .env

Make sure to set all required values in your `.env` file.

### 3. Set Up the Database

Before running this step, make sure `diesel_cli` is installed. See the instructions above if you haven’t done that yet.

    cd core
    diesel setup
    diesel migration run

## Running the API Server

From the project root, run the API crate:

    cargo run -p web_api
This will start the HTTP server on the address and port defined in your `.env` file

## User Management

You can manage users from the command line using the following commands:

### Create a new user:

    cargo run --bin create_user

### Reset password for an existing user:

    cargo run --bin reset_password

Both commands will prompt you for the necessary information (email, password, etc.).
