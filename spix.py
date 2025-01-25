#!/usr/bin/env python3

import sys
import asyncio
import traceback
from termcolor import colored
from spix_interpreter import SpixInterpreter  # Import SpixInterpreter from your file

async def main():
    if len(sys.argv) < 2:
        print(colored('Please provide a .spx file to execute', 'red'))
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, 'r') as file:
            code = file.read()
            interpreter = SpixInterpreter()
            await interpreter.execute(code)
    except Exception as e:
        print(colored(f'Error: {str(e)}', 'red'))
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
