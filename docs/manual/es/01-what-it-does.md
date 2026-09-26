# Qué hace

[English](../en/01-what-it-does.md) · **Español**

Todo lo que pueden hacer el firmware y sus herramientas, agrupado igual que el manual. El capítulo de cada grupo lo cuenta entero.

## Bancos y canciones

*En detalle: [Bancos](04-banks.md).*

- **32 bancos × 8 botones.** Una pulsación corta en Bank Up / Bank Down avanza un banco, una larga salta un número de bancos que tú eliges, y las dos dan la vuelta. Un comando `Bank` también puede ir directo a un banco concreto, así que un banco puede hacer de índice del setlist. Cada banco tiene un nombre que sale en la pantalla.
- **Setlist.** Bank Up / Down pueden seguir el orden que tú quieras en lugar del número de banco, de modo que las canciones de la noche salen una detrás de otra estén en el banco que estén. Los comandos Bank relativos también lo siguen; saltar a un banco concreto funciona igual que siempre.
- **Ver un banco antes de ir.** Con `Bank_Preview` activado, Bank Up / Down solo enseñan el banco al que irían, con su nombre invertido en la pantalla, y no envían nada; uno de los ocho botones lo confirma. Rozar un pulsador de banco en mitad de una canción ya no puede cambiarte el patch, y un banco que no confirmas se deshace solo.
- **Comandos al entrar y al salir de un banco.** Cada banco puede enviar unos comandos al llegar a él, normalmente un Program Change que elige su patch, sin gastar ningún botón en ello, y otros al salir, por ejemplo para apagar lo que encendió.
- **Segunda página en un banco.** Un botón pone los ocho botones y etiquetas de otro banco en lugar de los actuales, y vuelve, como una tecla de mayúsculas, y así duplica lo que cabe en una canción. Sigue siendo el mismo banco: Bank Up / Down, los pedales de expresión y el texto del ordenador siguen como estaban.
- **Los pulsadores Bank Up / Down también envían MIDI.** Cada uno tiene su propia lista de comandos para pulsación corta y larga, la misma en todos los bancos. `Bank_Switch_Mode` decide si además cambian de banco o si dejan de hacerlo del todo, lo que convierte la pedalera en un controlador sencillo de diez pulsadores.
- **Cuatro configuraciones en una pedalera.** Guarda hasta cuatro configuraciones completas, una por grupo o por sala, por ejemplo, y cambia entre ellas desde un botón. La pedalera enseña el número y el nombre de la elegida y vuelve a ella al apagarla y encenderla.
- **Cambios de banco desde MIDI.** Un Program Change o un Control Change que llega por USB puede elegir banco, así que una DAW u otra pedalera pueden llevar a esta.
- **Recordar el estado.** Si quieres, arranca en el último banco con cada toggle tal como lo dejaste, guardado en un diario repartido por varias páginas de flash para que el desgaste no sea un problema.

## Botones

*En detalle: [Botones](05-buttons.md).*

- **Pulsación larga.** Un segundo juego de hasta 10 comandos salta cuando mantienes un botón pisado más de un tiempo que tú eliges (500 ms por defecto). Los botones sin comandos de pulsación larga reaccionan al instante, como antes.
- **Pulsación doble.** Una tercera lista de comandos por botón, que se dispara con dos pisadas rápidas, además de la corta y la larga.
- **Dos pulsadores a la vez.** Pisar dos pulsadores juntos, el 3 y el 4 con un solo pie por ejemplo, ejecuta una lista propia en lugar de lo que hace cada uno por separado, como hacen las Boss y las Morningstar para llegar al afinador o al looper. Hasta doce parejas, en todos los bancos o en uno, y solo los pulsadores de una pareja esperan a ver si llega el otro.
- **Momentáneo o toggle** por comando, y soltado automático temporizado (hasta 1,27 s) para notas, Pitch Bend y teclas.
- **Enclavar o momentáneo.** Un botón toggle puede quedarse enclavado con un toque y funcionar como momentáneo si lo mantienes, como el boost de una Boss o una Morningstar: tócalo para dejarlo puesto toda la canción, o mantenlo pisado para un solo y se apaga al soltar.
- **Reiniciar al cambiar de banco.** Botón a botón, un toggle puede volver a apagado cada vez que sales de su banco, así que el boost empieza apagado en cada canción mientras la puerta de ruido se queda como la dejaste.
- **Grupos exclusivos.** Mete botones toggle de un banco en un grupo y al encender uno se apagan los demás, enviando sus comandos de apagado, como los botones de canal de un ampli o la elección entre varios delays.
- **Escenas.** Una pulsación pone los toggles del banco en la combinación que elijas, delay encendido y chorus apagado por ejemplo, pisando por ti solo los que no estaban ya así.
- **Botones de ciclo.** Un botón va pasando por varios estados, cada uno con sus comandos y su etiqueta en la pantalla: los cuatro canales de un ampli en un solo pulsador, una pisada cada uno, y vuelta a empezar.
- **Botones globales.** Un banco reservado guarda los botones que deben ser iguales estés donde estés —el afinador, el pánico, el tap— y cualquier botón de otro banco marcado como global lo toma todo de él: sus comandos, su etiqueta, su luz y si está encendido. Se escribe una vez, se cambia una vez, y está toda la noche bajo el mismo pie.
- **Toggles enlazados.** Con `Link_Toggles` activado, los botones toggle que envían el mismo CC o nota comparten su estado en todos los bancos: el delay encendido en una canción sale encendido en la siguiente, esté en el pulsador que esté.
- **Modos de LED** por botón: Normal, Reverse (encendido cuando está apagado) o AlwaysOn (parpadea mientras está activo). Los LEDs de Bank Up / Down tienen las mismas opciones. Brillo global para los LEDs encendidos y, aparte, para los encendidos en reposo, para que un botón activo destaque sobre uno en reposo.

## Comandos

*En detalle: [Comandos](06-commands.md).*

- **Hasta 10 comandos por pulsación**, enviados en orden. Cualquier mezcla de Program Change (con Bank Select opcional), Control Change, nota, Pitch Bend, Start, Stop, teclas de teclado USB y teclas multimedia, cada comando MIDI en su propio canal.
- **Pausas entre comandos.** Un comando `Wait` separa los comandos de un botón, para el equipo que se pierde un Control Change que llega justo detrás de un Program Change. La pedalera sigue leyendo pulsadores y pedales mientras espera.
- **Rampas de CC.** Un comando `Ramp` hace que el Control Change de debajo vaya hasta su valor poco a poco, en un tiempo de hasta unos 11 minutos, en lugar de saltar: un swell de volumen o un barrido lento de filtro con una sola pisada, y de vuelta al soltar o al apagar un toggle.
- **Valores y condiciones.** La pedalera guarda ocho valores propios, y un comando `Value` fija uno, le suma o le resta, dando la vuelta dentro de un tope que tú eliges. Un comando `If` encima de otro lo retiene salvo que se cumpla la prueba: el toggle de un botón encendido o apagado, uno de esos valores frente a un número, o el banco en el que estás. Así un botón puede hacer cosas distintas según otro —una capa de shift— y un contador en una pulsación larga puede recorrer unos cuantos patches pisada a pisada.
- **Macros.** Una lista de comandos guardada una vez y llamada desde muchos botones: los diez comandos que dejan listo el equipo de toda la banda viven en un botón, y cada banco que los quiera gasta un solo comando. Las macros llaman a macros, las pausas de dentro se respetan, y es la única función que devuelve espacio de configuración en lugar de gastarlo.
- **Un botón que pulsa otros.** El botón de la intro de una canción enciende el delay y lo ilumina, en este banco o en cualquier otro; un cambio de preset devuelve un botón a apagado sin enviar nada. Pulsar, encender solo si está apagado, apagar solo si está encendido, o solo poner el estado y el LED.
- **Un canal para todo, o varios a la vez.** Un ajuste de canal global lleva toda una configuración a otro canal, y un comando `Chan` envía el comando de debajo a tantos canales como quieras.
- **Preset siguiente y anterior.** Un botón sube o baja el Program Change desde donde estés, llegaras allí con un botón, entrando en un banco o desde el ordenador, y enseña el número nuevo en la pantalla. Se para en los extremos o da la vuelta, dentro del rango que tenga tu equipo.
- **CC relativo.** Un botón puede subir o bajar un valor de CC un paso en cada pisada, dando la vuelta si quieres, para ajustar un parámetro con el pie. El valor al que llega sale un momento en la pantalla, así que no ajustas a ciegas. Si lo mantienes pisado, puede seguir solo, cada vez más rápido, y un botón de preset siguiente o anterior también.
- **Control de grabadora y secuenciador.** Los comandos `MMC` manejan el transporte de una DAW o una grabadora —play, stop, grabar, rebobinar, ir a un tiempo— y los comandos `Song` eligen la canción de una caja de ritmos o un secuenciador y el punto donde empezar.
- **SysEx propio.** Se pueden guardar hasta dieciséis mensajes SysEx y enviarlos desde un botón, para equipos que solo se controlan así.
- **Teclado USB y teclas multimedia (HID).** Un comando puede pulsar una tecla con modificadores Ctrl / Shift / Alt / Cmd, darle un toque, mantenerla o soltarla, o enviar al ordenador una tecla multimedia (play/pausa, siguiente, anterior, stop, volumen, silencio, grabar).
- **Pánico.** Un comando que envía All Sound Off y All Notes Off en los dieciséis canales, por USB y por la salida DIN, para la nota colgada o el sonido desbocado en mitad de un bolo.

## Tempo

*En detalle: [Tempo, reloj, LFO y secuenciador](07-tempo.md).*

- **Tap tempo y reloj MIDI.** Un botón marca el tempo a golpes y otro arranca o para un reloj MIDI de 24 PPQN por USB y por la salida DIN, para que un delay o un looper sigan a tu pie. El tempo sale en la pantalla mientras marcas. El LED del botón de tap parpadea en cada pulso, sea el tempo tuyo o del ordenador. Cada banco o canción puede fijar además su propio tempo al entrar, y un par de botones pueden ajustarlo BPM a BPM.
- **Sigue el reloj del ordenador.** Con `Clock_Follow` activado, la pedalera mide el reloj MIDI que llega por USB, adopta ese tempo y lo enseña en la pantalla durante 1,5 segundos, y aparta su propio reloj mientras suena el del ordenador. Si el reloj del ordenador se para, el de la pedalera sigue al mismo tempo.
- **LFO sincronizado al tempo.** Un comando `LFO` hace que el Control Change de debajo suba y baje solo, un ciclo por cada figura del tempo (de un tresillo de semicorchea a cuatro compases) con forma senoidal, triangular, de sierra, cuadrada o aleatoria: trémolo, barridos de filtro y auto-pan que siguen tu tap o el reloj del ordenador.
- **Secuenciador por pasos.** Una serie de comandos `Seq` convierte el Control Change o la nota de debajo en una secuencia: un valor por paso, a corcheas o a la figura que elijas, dando vueltas mientras mantienes el botón o mientras su toggle está encendido. Con silencios incluidos, así que es tanto ritmo como melodía: un filtro entrecortado, un arpegio, un patrón de cambios de canal del ampli, todo a tempo con el tap o con el reloj del ordenador.

## Pedales de expresión

*En detalle: [Pedales de expresión](08-expression.md).*

- **Dos pedales de expresión** con número de CC, canal MIDI, extremos calibrados, curva de respuesta y sentido propios de cada uno, calibrados en directo desde el configurador. Cada uno puede hacer además de interruptor: llegar a la punta, o volver al talón, pulsa un botón del banco actual.
- **Expresión por banco.** Cada banco puede dar a cada pedal de expresión su propio CC y canal, o silenciarlo, así que el mismo pedal es un wah en un banco y un volumen en otro.
- **Destino del pedal desde un botón.** Un comando cambia lo que envía un pedal de expresión, su CC y su canal, o lo silencia, de modo que un pedal puede ser el wah, luego el volumen, luego un parámetro, dentro del mismo banco; como toggle, al apagarlo el pedal vuelve a lo suyo.
- **Wah con auto-engage.** Levantar un pedal de expresión desde el talón enciende un botón, y dejarlo un momento en el talón lo vuelve a apagar, como los wah con auto-engage de Fractal y Line 6: no hay que pisar el wah antes de usarlo.
- **Rango de salida del pedal.** Un pedal puede enviar solo parte del rango, de 40 a 127 para un volumen que nunca llega al silencio por ejemplo, o funcionar al revés; por pedal, y además por banco.
- **Pitch Bend y CC de 14 bits desde un pedal.** Un pedal de expresión puede enviar Pitch Bend, para un whammy, o una pareja de CC de 14 bits, con 16384 pasos en lugar de 128, para barridos sin escalones en los sintes y plugins que los leen.
- **Un pedal de expresión como velocidad de los LFO y las secuencias.** En lugar de un CC, un pedal puede marcar lo rápido que van todos los LFO y secuencias por pasos, lento en el talón y rápido en la punta, siempre en una división de nota del tempo: un trémolo que se acelera bajo tu pie sin salirse de tempo.

## La pantalla

*En detalle: [La pantalla](09-the-display.md).*

- **Etiquetas de los botones en la pantalla.** Cada botón tiene una etiqueta de 4 caracteres; la pantalla enseña el banco actual y una cuadrícula de 2×4 que refleja la pedalera, con los toggles dibujados invertidos mientras están encendidos.
- **El ordenador escribe en ella.** Una DAW, MainStage o un script pueden poner el nombre del patch o de la canción en la pantalla por SysEx: en lugar del nombre del banco, de su información o a lo ancho de toda la línea de arriba en letras grandes o pequeñas, hasta que cambia el banco, para siempre o un momento. Un nombre más largo que su sitio lo recorre una vez, al llegar y cada vez que entras en un banco, y luego enseña su principio. `Send_Text.py` lo envía desde un terminal, o imprime los bytes para que los envíe otro programa.
- **Un banner al encender.** El nombre de la configuración y la versión del firmware pueden cruzar la pantalla en letras grandes mientras arranca la pedalera, así ves de un vistazo qué configuración ha cargado. O un texto tuyo, de hasta 60 caracteres, que la pedalera conserva cargues la configuración que cargues: un grupo, un espectáculo, un teléfono por si se pierde. Cualquier pulsador lo corta, y la pedalera responde desde la primera pisada. Se activa con `Boot_Banner`; mira [El texto propio del banner](09-the-display.md#el-texto-propio-del-banner).

## En la pedalera, sin ordenador

*En detalle: [Editar en la pedalera](10-editing-on-the-pedal.md).*

- **Editar en la pedalera.** Bank Down y Bank Up pisados a la vez abren un editor en la propia pantalla de la pedalera: los comandos de cualquier botón de cualquier banco, pulsación corta y larga, sus etiquetas, y los ajustes que son un número o una opción, todo cambiado con el pie y escrito directamente en la flash. Para el Program Change equivocado que descubres en la prueba de sonido sin un portátil a mano.
- **Modo seguro.** Mantén pisado cualquiera de los ocho pulsadores de comando mientras enciendes la pedalera y arranca sin enviar nada: ni comandos al entrar en el banco, ni banco o toggles guardados, ni la baliza del Kemper, ni la posición de los pedales de expresión. Aun así cambia de banco, responde a sus botones y abre el editor, así que una configuración que silencia el ampli o descoloca el equipo al arrancar se puede arreglar sin ordenador. Mira [Modo seguro](10-editing-on-the-pedal.md#modo-seguro).
- **Funciona sin ordenador.** Con un cargador USB o una batería externa la pedalera funciona con normalidad y maneja tu equipo por la salida DIN.
- **Reposo por inactividad.** Tras los minutos que elijas sin que nadie la toque, la pantalla y los LEDs se apagan. Cualquier pisada o movimiento de un pedal de expresión los vuelve a encender, y la pisada que la despierta sigue haciendo su trabajo, así que en el escenario no se pierde nada.
- **Sigue funcionando cuando el ordenador duerme.** Si el ordenador al que está conectada entra en reposo y sigue dando corriente por el puerto USB, la pedalera sigue funcionando: la pantalla, los LEDs y el MIDI DIN como siempre, y el MIDI por USB se descarta hasta que vuelva un ordenador.
- **Se reinicia sola si alguna vez se cuelga.** Un watchdog nota cuando el firmware deja de funcionar y reinicia la pedalera, que vuelve a estar lista unos seis segundos después, en vez de quedarse muerta hasta apagarla y encenderla. Vuelve a donde estaba: al mismo banco, con los mismos toggles encendidos y el mismo tempo, diga lo que diga `Remember_State`, y muestra RESTARTED un momento. Una pantalla que deja de responder, por electricidad estática o un flex suelto, tampoco congela ya la pedalera: sigue funcionando y la pantalla se vuelve a enviar.

## Con un ordenador y otros equipos

*En detalle: [Plantillas y equipos](11-devices.md).*

- **LEDs que siguen al ordenador.** Con `LED_Feedback` activado, un CC o una nota que llega por USB enciende o apaga los botones toggle que lo envían, así que la pedalera enseña lo que de verdad está encendido cuando cambias un efecto desde una DAW o desde el editor del ampli. A un equipo que informa en otro CC distinto del que recibe, o con otros valores, se le sigue con un comando `Listen` en el botón, y con varios en un mismo CC el LED parpadea rápido, despacio o queda tenue según el valor, así que se distingue de un vistazo si un looper graba, sobregraba o reproduce.
- **Pisada desde el ordenador.** Con `Remote_Mode` activado, diez CC o notas que llegan por USB pisan los diez pulsadores, mantenidos tanto tiempo como el ordenador los mantenga, así que una DAW, MainStage o un script pueden usar la lógica de la propia pedalera: toggles, pulsaciones largas y dobles, cambios de banco, LEDs y pantalla.
- **MIDI thru de USB a DIN.** Si quieres, reenvía a la toma MIDI OUT todo lo que llega por USB, para que la pedalera haga también de interfaz MIDI USB del equipo que tiene detrás. Clock / Start / Continue / Stop tienen su propio interruptor.
- **Aguanta el Active Sensing.** Algunos equipos, entre ellos el Kemper Profiler Player, envían un byte de Active Sensing cada 300 ms. Un controlador que nunca lo lee deja que se llene su búfer USB hasta que la conexión se atasca, que es lo que hace que el firmware de fábrica arrastre al otro equipo hasta dejarlo casi parado. Aquí se lee cada evento MIDI que llega por USB y el endpoint se rearma siempre, así que la corriente de datos no puede atascarse.
- **Kemper en las dos direcciones.** Con `Kemper_Mode` activado, la pedalera le pregunta al ampli por su estado y sigue sus respuestas: el rig en el que estás escrito junto al nombre del banco y los módulos de efecto encendiendo los botones que los activan, tanto si cambiaste el módulo con el pie, en el ampli o desde cualquier otro sitio; mira [Kemper en las dos direcciones](11-devices.md#kemper-en-las-dos-direcciones).
- **Lista para el Fractal FM3.** Una plantilla que carga un preset por banco y pone escenas, afinador, tap tempo, el looper y el bypass de bloques bajo tus pies; mira [la plantilla del FM3](11-devices.md#plantilla-para-fractal-audio-fm3).
- **Lista para el Line 6 HX Stomp.** Una plantilla con un preset por banco, snapshots, los pulsadores FS1–FS5, afinador, tap tempo y el looper, usando el mapa MIDI propio del HX Stomp, así que no hay nada que asignar; mira [la plantilla del HX Stomp](11-devices.md#plantilla-para-line-6-hx-stomp).
- **Lista para el Kemper Profiler Player.** Una plantilla con los diez bancos de cinco rigs del Player, sus módulos y botones de efecto, afinador y tap tempo, de nuevo sin nada que asignar en el Player; mira [la plantilla del Kemper Player](11-devices.md#plantilla-para-kemper-profiler-player).

## Las herramientas

*En detalle: [El configurador](03-the-configurator.md).*

- **Pedalera virtual.** El configurador dibuja la pedalera tal como es, y te deja pisar sus pulsadores con el ratón —un toque, mantener o doble clic— mientras su pantalla, píxel a píxel, y sus LEDs se leen de la pedalera, así que puedes probar una configuración sin ponerte encima.
- **Configuración por USB.** Carga una configuración en la pedalera y léela de vuelta, desde la interfaz gráfica o desde la línea de comandos, por SysEx MIDI USB normal y corriente. Sin drivers especiales.
- **Ordenar un repertorio.** Sube y baja bancos en la lista, o llévalos a cualquier sitio de una vez, y todos los cambios de banco, el setlist, las macros y las combinaciones los siguen; copia un banco o un solo botón sobre otro.
- **Aprender por MIDI.** Pulsa Learn en un comando y mueve un mando o pulsa un botón del aparato: su tipo, canal y número se rellenan solos, desde cualquier entrada MIDI del ordenador.
- **Monitor MIDI.** Cada mensaje que llega al ordenador, de la pedalera o de cualquier otra entrada, con su tiempo al milisegundo y leído en claro junto a sus bytes, con filtros por tipo, canal y puerto.
- **Copias de seguridad.** Copia las cuatro ranuras de configuración a una carpeta de una vez, un CSV editable por ranura, y vuelve a ponerlas todas igual de fácil.
- **Actualizar el firmware sin mantener nada pisado.** Desde el firmware 0.58 la pedalera se reinicia en modo DFU cuando se lo pide el ordenador, así que `Update_Firmware.py` o **Update Firmware…** en el configurador hacen toda la actualización en unos quince segundos: sin pulsadores pisados al encender, sin apagar y encender, y con la configuración intacta. El bootloader de fábrica nunca se toca.

---

[Índice](README.md) · [Primeros pasos →](02-getting-started.md)
