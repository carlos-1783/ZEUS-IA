import sys
import os
from pathlib import Path

# Redirigir la salida estándar y de error a archivos
sys.stdout = open('test_output_stdout.txt', 'w', encoding='utf-8')
sys.stderr = open('test_output_stderr.txt', 'w', encoding='utf-8')

# Mensaje de prueba
print("=== PRUEBA DE SALIDA ===")
print(f"Directorio actual: {os.getcwd()}")
print(f"Python version: {sys.version}")
print("Listando directorio actual:")
for item in os.listdir('.'):
    print(f"- {item}")

# Cerrar los archivos de salida
sys.stdout.close()
sys.stderr.close()

# Restaurar salida estándar
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

print("Prueba completada. Ver archivos 'test_output_stdout.txt' y 'test_output_stderr.txt'")
