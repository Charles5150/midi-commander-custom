# Herramientas de línea de comandos

[English](../en/13-command-line-tools.md) · **Español**

Todo lo que hace el configurador se puede hacer también desde un terminal, que viene bien para scripts, copias de seguridad y un flasheo rápido antes de un bolo. Ejecuta las herramientas desde la raíz del repositorio, con la pedalera conectada por USB en modo normal, no en modo DFU.

Las herramientas encuentran la pedalera por su nombre MIDI USB, `MIDI Commander Custom`, y comprueban la versión de su firmware antes de hacer nada.

## Elegir una ranura de configuración

`CSV_to_Flash.py` y `Flash_to_CSV.py` trabajan sobre una de las cuatro [ranuras de configuración](04-banks.md#cuatro-configuraciones) de la pedalera:

- `--slot 1` a `--slot 4` elige la ranura;
- si no lo pones, usan la ranura que está usando la pedalera.

Si lees una ranura vacía, te lo dicen en lugar de sacar un CSV. El firmware anterior a la 0.24 tiene una sola configuración, y con él las herramientas rechazan cualquier ranura que no sea la 1.

## CSV_to_Flash: enviar una configuración a la pedalera

```bash
.venv/bin/python python/CSV_to_Flash.py my-config.csv
.venv/bin/python python/CSV_to_Flash.py --slot 2 my-config.csv
```

Comprueba el CSV, dice cuánto ocupa la configuración y pregunta `Continue? (y/N)` antes de escribir nada; `--yes` o `-y` se salta la pregunta. Luego escribe la ranura y reinicia la pedalera.

## Flash_to_CSV: leer una configuración de vuelta

```bash
.venv/bin/python python/Flash_to_CSV.py current-config.csv
.venv/bin/python python/Flash_to_CSV.py --slot 3 slot3.csv
```

Escribe lo que tiene la pedalera en un CSV que puedes abrir en el configurador, incluido cualquier cambio hecho con el [editor de la pedalera](10-editing-on-the-pedal.md).

## Copias de seguridad

`Backup_Slots.py` copia las cuatro ranuras a una carpeta de una vez, y las vuelve a poner.

```bash
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup
```

**backup** lee a la carpeta cada ranura que tenga una configuración:

- `slot1.csv` a `slot4.csv`, cada uno una configuración normal que se puede abrir en el configurador o cargar por separado;
- `backup.txt`, con la fecha, el firmware y el nombre de cada ranura.

Si no le das carpeta, crea una con la fecha y la hora como nombre.

**restore** vuelve a poner una carpeta de copia:

1. Comprueba cada archivo antes de tocar la pedalera.
2. Enumera las ranuras que va a sobrescribir y pregunta antes; `--yes` o `-y` se salta la pregunta.
3. Escribe cada archivo en su ranura, y reinicia la pedalera una sola vez al final.

Las ranuras sin archivo en la carpeta se quedan como están. Una copia restaurada da los mismos bytes de los que se leyó, salvo que los ajustes que nunca tuvo una configuración de un firmware anterior se escriben con el valor que ya usaba la pedalera para ellos.

## Send_Text: escribir en la pantalla

```bash
.venv/bin/python python/Send_Text.py "Sweet Child"
.venv/bin/python python/Send_Text.py --banner "The Band  612 345 678"
```

Pone un texto en la línea de arriba de la pedalera, o con `--hex` imprime los bytes SysEx para que los envíe otro programa; con `--banner` lee, guarda o borra el texto propio del banner. Mira [Texto desde el ordenador](09-the-display.md#texto-desde-el-ordenador) y [El texto propio del banner](09-the-display.md#el-texto-propio-del-banner).

## Kemper_Sim: un Kemper para probar Kemper_Mode sin tenerlo

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

Responde a la pedalera como lo haría un Kemper Profiler, por la misma conexión USB que usa un Player. En su prompt:

| Comando | Qué hace |
|---|---|
| `rig <name>` | pone nombre al rig que enseña la pedalera |
| `a`, `b`, `c`, `d` | enciende o apaga el Stomp A, B, C o D |
| `x`, `mod`, `dly`, `rev` | lo mismo con los demás módulos |
| `show` | lo que se supone que está haciendo el ampli |
| `quit` | termina |

Mira [Kemper en las dos direcciones](11-devices.md#kemper-en-las-dos-direcciones).

## Update_Firmware: actualizar el firmware

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

Comprueba el archivo `.dfu`, pregunta antes de flashear (`--yes` se salta la pregunta), pone la pedalera en modo DFU, la flashea y la vuelve a arrancar, sin mantener nada pisado con el firmware 0.58 o posterior. Mira [Actualizar el firmware más adelante](02-getting-started.md#actualizar-el-firmware-más-adelante).

## Stress_Test y Latency_Test: poner a prueba la pedalera

```bash
.venv/bin/python python/Stress_Test.py      # work the pedal hard for a minute and check it is still sound
.venv/bin/python python/Latency_Test.py     # how long a press takes to leave as MIDI, quiet and under load
```

`Stress_Test.py` le da caña a la pedalera durante un minuto y comprueba que sigue en forma; `Latency_Test.py` mide cuánto tarda una pisada en salir como MIDI, en reposo y con carga. Las dos necesitan la configuración de demostración, `python/demo-all-features.csv`, en la pedalera, y ningún pie. Se describen en [CONTRIBUTING](../../../CONTRIBUTING.md#tests) (en inglés).

## Ver lo que envía la pedalera

Cualquier monitor MIDI lo enseña: MIDI Monitor en macOS, MIDI-OX en Windows, o `aseqdump -p 'MIDI Commander Custom'` en Linux.

<details><summary>Por dentro</summary>

Las herramientas intercambian la configuración como mensajes SysEx con el ID de fabricante `0x7D`:

| Comando | Número |
|---|---|
| borrar | 52 |
| escribir un bloque de 16 bytes | 54 |
| leer un bloque | 56 |
| versión | 58 |
| reiniciar | 60 |
| lecturas de los pedales | 62 |
| elegir una ranura | 64 |
| pisar un pulsador | 66 |
| el estado de la pedalera | 68 |
| la pantalla de la pedalera | 70 |
| poner texto en la pantalla | 72 |
| reiniciar en modo DFU, con los bytes de comprobación `44 46` | 74 |
| el texto propio del banner | 76 |
| la latencia de las últimas pisadas | 78 |

Los comandos de lectura necesitan el firmware 0.2 o posterior; las herramientas te avisan si la pedalera tiene uno anterior.

</details>

---

[← El archivo de configuración](12-configuration-file.md) · [Índice](README.md)
