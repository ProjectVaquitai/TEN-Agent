#!/bin/bash

# Build playground
docker build -t ten_agent_playground -f ./playground/Dockerfile ./playground

# Build server
docker build -t ten_agent_dev -f Dockerfile.dev .

# Run docker-compose up
docker-compose up
