# Instalador para Windows

El instalador se construye para Windows 10/11 de 64 bits y deja una aplicacion
autocontenida. El computador donde se instala no necesita Python, pip,
Playwright ni Chromium previamente instalados.

## Construccion

Ejecute PowerShell desde la raiz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_gui.ps1
```

El script crea un entorno de compilacion, instala `requirements.txt` y
`requirements-gui.txt`, ejecuta `playwright install chromium`, empaqueta la GUI
con PyInstaller y compila el instalador con Inno Setup. Durante la compilacion
tambien verifica que el modulo de Chrome de Selenium quede dentro del paquete;
si falta, detiene la compilacion y no genera un instalador incompleto.

El resultado queda en:

```text
installer_output\Setup_ContratacionesETL_0.5.0.exe
```

Al instalar, el acceso directo abre directamente la GUI equivalente a:

```text
python -m desktop
```

Las credenciales deben configurarse en el archivo `.env` del directorio de la
aplicacion usando `.env.example` como plantilla. El instalador no contiene
credenciales reales.

El flujo UISARD/Alfresco usa Selenium y requiere que el equipo tenga Google
Chrome instalado. Python, pip, Selenium, Playwright y Chromium de Playwright
no necesitan instalarse por separado.
