# URL and Payment Processors Input Contract

Este documento define el segundo set de productos de datos del repositorio: presencia digital de plataformas de apuestas online y procesadores de pago asociados.

## Tesis editorial

Los procesadores de pago cumplen un rol estructural en el funcionamiento economico de las casas de apuestas online no autorizadas en Chile. Permiten que usuarios ubicados en Chile depositen dinero mediante medios locales, como tarjetas, transferencias o billeteras digitales, y canalizan esos fondos hacia operadores usualmente domiciliados fuera del pais.

Tambien hacen posible el pago de premios. Ese flujo de entrada y salida de dinero entrega operatividad y credibilidad al sistema. Por eso, para este producto los PSP no se tratan como actores accesorios, sino como infraestructura financiera necesaria para que los sitios puedan funcionar como negocio real.

## Alcance del producto

El producto busca registrar, con evidencia verificable:

- URLs activas o historicas asociadas a marcas de apuestas online observadas en Chile.
- Dominio, subdominio y ruta relevante donde se observa operacion o acceso local.
- Procesadores de pago identificados en flujos de deposito, retiro, checkout, pasarelas o terminos de pago.
- Medios de pago disponibles para usuarios en Chile.
- Evidencia asociada: capturas, URLs archivadas, fecha de observacion y notas de verificacion.

La presencia de un PSP en el producto no constituye una imputacion penal ni una conclusion juridica definitiva. Indica que, segun la evidencia disponible, aparece vinculado al flujo operativo o transaccional de una plataforma observada.

## Insumo esperado

Carpeta sugerida para archivos crudos:

- `input/url_payment_processors/`

Formato recomendado inicial para tabla plana:

- `.csv` o `.xlsx`
- Una fila por observacion verificable.
- Si una misma URL usa multiples PSP, se recomienda una fila por combinacion `brand_name` + `url` + `payment_processor`.

Formato actualmente soportado:

- `.xlsx`
- Hoja tipo matriz.
- Columna `A`: marca o casa de apuesta.
- Columna `B`: medio de pago o procesador observado.
- Columnas siguientes: fechas de observacion codificadas como fecha Excel.
- Celdas de cruce: `si` / `no`, indicando si ese medio o procesador aparece disponible para esa marca en esa fecha.

El primer archivo crudo procesado con este contrato es `input/url_payment_processors/Casas de apuestas 2.xlsx`. Ese archivo no incluye URLs ni dominios; por eso las salidas de dominios quedan disponibles con encabezados, pero sin filas hasta recibir evidencia URL.

## Columnas fuente esperadas

Campos minimos:

- `observed_at`: fecha de observacion en formato `YYYY-MM-DD`.
- `brand_name`: marca o plataforma observada.
- `url`: URL completa observada.
- `domain`: dominio normalizado, sin protocolo ni ruta.
- `payment_processor`: nombre del procesador de pago identificado.
- `payment_flow`: tipo de flujo observado, por ejemplo `deposit`, `withdrawal`, `checkout`, `terms`, `support`.
- `payment_method`: medio de pago visible, por ejemplo `card`, `bank_transfer`, `wallet`, `crypto`, `unknown`.
- `evidence_url`: enlace a evidencia verificable, captura, archivo o fuente.
- `verification_status`: estado editorial de verificacion.

Campos opcionales:

- `country_context`: pais o mercado al que apunta la observacion.
- `legal_entity`: razon social visible, si aparece en la evidencia.
- `psp_country`: pais asociado al PSP, si esta documentado.
- `capture_path`: ruta local a captura o archivo de respaldo.
- `notes`: notas editoriales breves.

## Normalizacion prevista

- `brand_name` y `payment_processor` se normalizan a mayusculas limpias.
- `url` se conserva completa para trazabilidad.
- `domain` se deriva desde `url` cuando venga vacio.
- `observed_at` se valida como fecha ISO.
- `payment_flow`, `payment_method` y `verification_status` se reducen a vocabularios controlados.
- Se deduplican observaciones identicas por `observed_at`, `brand_name`, `url` y `payment_processor`.

## Productos esperados

Carpeta de salida:

- `output/data_products/infraestructura_pagos_urls/`

Tablas previstas:

- `url_payment_processor_detail.csv`: detalle normalizado de observaciones.
- `payment_processors_by_brand.csv`: matriz marca x PSP.
- `domains_by_brand.csv`: URLs y dominios observados por marca.
- `payment_labels_by_brand.csv`: matriz marca x rotulo original observado.
- `payment_methods_by_brand.csv`: medios de pago disponibles por marca.
- `network_edges.csv`: aristas para grafo `brand -> domain -> payment_processor`.
- `summary.json`: resumen para visualizacion en GitHub Pages.

## Indicadores editoriales

Indicadores iniciales recomendados:

- Numero de marcas con al menos un PSP identificado.
- Numero de PSP distintos observados.
- Numero de dominios y subdominios asociados a cada marca.
- PSP compartidos por multiples marcas.
- Marcas con medios de pago locales visibles para Chile.
- Observaciones verificadas, pendientes y descartadas.

## Criterio de publicacion

Una observacion deberia publicarse solo si tiene evidencia trazable y fecha de observacion. Cuando la evidencia sea sensible, puede publicarse una referencia resumida y mantener el respaldo fuera del repositorio publico.
