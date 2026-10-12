# Schemas locais de OpenLineage

Os quatro schemas oficiais e a licença Apache-2.0 foram copiados sem alterações da tag [OpenLineage 1.39.0](https://github.com/OpenLineage/OpenLineage/tree/1.39.0), commit `4e4a9186962094ce5fd29c5e4bc9d5ddb5fa39a8`. O schema principal identifica a especificação `2-0-2`. Os arquivos permanecem disponíveis no pacote instalado, mesmo com o batch sem rede.

| Arquivo | SHA-256 dos bytes upstream |
| --- | --- |
| `OpenLineage.json` | `69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2` |
| `SchemaDatasetFacet.json` | `b1ed03c11391ebb89ffc5212f303702a46cc0f528dbf1ddeb591616288c8c10f` |
| `DatasetVersionDatasetFacet.json` | `91f57b67bc6d639bb6d600e26b827dac551e3520a233d1785d65870da263dc34` |
| `ErrorMessageRunFacet.json` | `b11b4ee8b0f99f6846264f87cad48390255c7ef142ce623216660c7097be0ea6` |
| `OpenLineage-LICENSE.txt` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

Copyright 2018-2024 contributors to the OpenLineage project. A [licença original](OpenLineage-LICENSE.txt) acompanha os arquivos. O adaptador verifica os hashes oficiais antes de carregar os schemas; os testes também conferem os bytes.

`VarejoFacets.json` é o contrato local do projeto. Suas definições seguem os nomes `VarejoOutcomeRunFacet`, `VarejoTimingRunFacet` e `VarejoProvenanceDatasetFacet`; as chaves dos eventos são `varejo_outcome`, `varejo_timing` e `varejo_provenance`. Cada `_schemaURL` é `urn:sha256:<hash dos bytes de VarejoFacets.json>#/$defs/<definição>`. A URN identifica conteúdo imutável; consumidores devem registrar o arquivo local nesse identificador. Uma mudança nos bytes cria outro identificador.

O registro local associa as URLs upstream, os `$id` oficiais e a URN própria aos arquivos. A validação usa JSON Schema Draft 2020-12, com checagem de UUID, data, data/hora e URI. `rfc3339-validator` e `rfc3986-validator` são dependências explícitas porque instalar apenas `jsonschema` pode deixar esses formatos sem validação. A ausência de um validador obrigatório provoca erro.
