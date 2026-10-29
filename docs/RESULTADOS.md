# Validação em dois aparelhos — 29/10/2026

Os dois Redmi A5 tinham o perfil descrito no README e o parâmetro `disable_factoryreset=1`. Não foi usada uma imagem compartilhada: cada alteração foi preparada a partir do dump do respectivo aparelho.

| Evidência | Unidade A | Unidade B |
|---|---|---|
| Estado inicial | Falha ao iniciar; reset indisponível/falhava | Falha ao iniciar; reset falhava |
| Log | `config.disable_format=1` | `config.disable_format=1` |
| Partição `rescue` | 134217728 bytes | 134217728 bytes |
| Mudança | Um byte: `1` → `0` | Um byte: `1` → `0` |
| Offset na imagem | 44040213 | 50335765 |
| Conferência integral pós-gravação | SHA-256 igual ao esperado | SHA-256 igual ao esperado |
| Restauração pelo Recovery | Concluída | Concluída |
| Android iniciou | Confirmado pelo operador | Confirmado pelo operador |

Os offsets acima são evidência de que **não se deve usar um offset fixo**; não são instruções para editar outro dump. As imagens e seus logs completos permanecem privados.

Não foram necessários root, desbloqueio permanente do bootloader, troca de ROM, alteração de `persist`, partições de modem ou calibração. O comando `reboot-recovery` do `spd_dump` escreveu a solicitação de entrada no Recovery na área BCB de `misc`, comportamento esperado e distinto da edição de `rescue`.

## Tentativas que não resolveram

- Limpeza por Fastboot: recusada pelo bootloader bloqueado.
- `adb rescue wipe userdata`: falhou antes da descoberta do parâmetro.
- Reinstalação pelo `adb rescue install`: não confirmou sucesso e não resolveu o caso. O contador em 47% não é uma medida direta de avanço da instalação; não foi usado como prova isolada de travamento.
- Selecionar Factory data reset antes da correção: voltava ao erro; os registros indicavam que a formatação estava desabilitada.
- Driver SPRD antigo de 2015: instalou no Windows, mas não carregou, com código 52. Foi substituído por WinUSB; não se desativou a verificação de assinaturas.

## Limitações

São dois casos, mesma versão de firmware. O retorno ao Android foi informado pelo operador; não houve ensaio prolongado de hardware, atualização futura ou auditoria de todos os binários de terceiros. Não se determinou como surgiu o parâmetro ou a falha original de dados. Não se demonstrou suporte a outras versões, variantes, armazenamentos ou aparelhos.
