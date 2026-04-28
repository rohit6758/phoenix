# Start with a Linux machine that has Python
FROM python:3.9-slim

# Install Compilers and Runtimes for Multi-Language Support
# g++ (C++), gcc (C), default-jdk (Java), nodejs (JavaScript)
RUN apt-get update && \
    apt-get install -y g++ gcc default-jdk nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy our Phoenix Engine code into the cloud
WORKDIR /app
COPY . /app

# Install Python requirements
RUN pip install -r requirements.txt

# Open the port
EXPOSE 5000

# Start the Engine!
CMD ["python", "engine.py"]