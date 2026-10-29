# Redmi A5: `set_policy_failed:/data/per_boot` com reset bloqueado

[English guide](docs/ENGLISH.md) · [Procedimento técnico](docs/PROCEDIMENTO.md) · [Resultados](docs/RESULTADOS.md)

Procedimento documentado após recuperar **dois Redmi A5** em 29/10/2026. Ambos exibiam `NEED TO WIPE USERDATA` / `set_policy_failed:/data/per_boot`, mas a restauração de fábrica falhava. A causa confirmada do **bloqueio do reset** era um parâmetro persistido na partição `rescue`:

```text
/cache/recovery/last_extension_parameters
disable_factoryreset=1
```

O Recovery lia esse arquivo e registrava:

```text
Start to read extension parameters
disable_factoryreset=1
config.disable_format=1
WipeData disable_format is true
```

Mudamos **somente o caractere `1` para `0` nesse arquivo**, dentro de uma cópia da partição `rescue` de cada aparelho. Depois da gravação, lemos toda a partição de volta, comparamos SHA-256 e usamos **Factory data reset** no próprio Recovery. Os dois aparelhos voltaram a iniciar o Android, segundo confirmação do operador.

**Isso explica por que o reset estava bloqueado; não estabelece a causa original da falha em `/data/per_boot`, nem quem gravou o parâmetro.** Não é uma correção universal para todo bootloop ou todo erro de criptografia.

## Perfil testado

| Item | Observado |
|---|---|
| Modelo | Redmi A5, `25028RN03A` / `serenity` |
| Sistema | Android 15 Go, `A15.0.13.0.VGWMIXM` |
| Chip | UNISOC T7250 / UMS9230E |
| Memória | eMMC; dois aparelhos com `userdata` de aproximadamente 110473 MiB |
| Bootloader | Bloqueado; não foi necessário desbloqueá-lo permanentemente |
| Slot | `a` nos dois aparelhos |
| `rescue` | 128 MiB, ext4, montada como `/cache` no Recovery |
| Host | Windows 11, Python 3.15; ferramenta offline usa apenas biblioteca padrão |

Use somente em aparelho próprio ou sob sua administração autorizada. **A restauração apaga os dados pessoais.** O acesso BROM executa loaders de terceiros e uma falha de gravação pode exigir recuperação técnica. Contas Google, FRP e políticas de gerenciamento não são removidas por este projeto. Se o bloqueio de reset for uma política legítima de gerenciamento, resolva-a com o administrador responsável.

## O que está disponível aqui

- `rescue_config.py`: inspeciona e prepara **uma cópia local** de uma imagem ext4. Não conecta ao USB, não executa exploit, não desbloqueia e não grava o celular.
- `tests/`: testes com imagens sintéticas, sem dados dos aparelhos.
- `Redmi-A5-BROM.cfg`: preset do Zadig limitado ao USB ID `1782:4D00`.
- Documentação dos comandos usados, limitações, conferência e recuperação do original.

**Não há firmware, dumps, logs completos, imagens de partições, drivers ou binários de exploit neste repositório. Nunca use o dump `rescue` de outra pessoa.** O offset do parâmetro foi diferente nos dois aparelhos testados.

## Uso da ferramenta offline

Leia primeiro o [procedimento completo](docs/PROCEDIMENTO.md). Os exemplos abaixo só preparam arquivos locais.

```powershell
# Inspecionar sua própria cópia de rescue
python rescue_config.py inspect private/rescue-original.img

# Conferir o arquivo também com uma ferramenta independente, como 7-Zip.
# Extraia recovery/last_extension_parameters para private/extracted/.

# Preparar uma cópia: recusa sobrescrever o original ou uma saída existente
python rescue_config.py patch private/rescue-original.img --reference-file private/extracted/recovery/last_extension_parameters --output private/rescue-patched.img

# Depois da gravação manual e de uma leitura COMPLETA de volta
python rescue_config.py verify private/rescue-patched.img private/rescue-readback.img
```

O programa resolve diretórios, inode e extents; não faz substituição global de texto e não usa offset fixo. Recusa tamanho diferente de 128 MiB, conteúdo inesperado, filesystem sujo, journal pendente, layout de 64 bits, metadata checksums, extents não suportados e imagem já corrigida. Uma recusa é motivo para inspeção especializada, não para remover as verificações.

```powershell
python -m unittest discover -s tests -v
```

## Ferramentas e créditos

- [TomKing062 — CVE-2022-38694](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader): acesso BROM e pacote UMS9230E. O pacote UMS9230 genérico não é substituto do UMS9230E.
- [TomKing062 — spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash) e [builds Windows](https://github.com/TomKing062/action_spd_dump_it): comunicação `spd_dump`.
- [Relato específico do Redmi A5, issue 327](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader/issues/327) e [relato de falha/recuperação, issue 262](https://github.com/TomKing062/CVE-2022-38694_unlock_bootloader/issues/262): contexto e limitações do método. Este projeto não recomenda executar o desbloqueador automático.
- [Zadig oficial](https://zadig.akeo.ie/) e [manual](https://github.com/pbatard/libwdi/wiki/Zadig): associação WinUSB.
- [7-Zip](https://www.7-zip.org/): inspeção independente da imagem ext4.

Pesquisa, execução e validação prática: **Tiago Rafael**, com assistência do Codex. Licença MIT para o código e a documentação originais deste repositório; ferramentas externas mantêm suas próprias licenças.

Para contribuir, informe modelo, firmware, tamanho de `rescue` e apenas mensagens relevantes já anonimizadas. Não envie número de série, IMEI, contas, logs integrais nem imagens de partição.
