# Security

Report a vulnerability privately to security@axius-sdc.com, or through GitHub's
private vulnerability reporting on this repository. The organization policy is
at https://github.com/SemanticDataCharter/.github/blob/main/SECURITY.md. Expect an
acknowledgement within three business days.

## Supported versions

| version | supported |
|---|---|
| 4.2.x | yes |
| earlier | no |

## The MCP server, as a threat model

`sdcgovernance serve --mcp` speaks JSON-RPC over stdio. There is no authentication and no
network listener: whoever can write to the process's stdin is the caller, and
that caller controls every byte of every argument, including any file path a
tool accepts. The server is designed for that:

- **Malformed input is answered, never fatal.** A JSON value that is not an
  object, `params` that is not an object, a non-string method or tool name, or
  tool `arguments` that are not an object are answered with JSON-RPC `-32600`
  or `-32602`, and the loop keeps reading. A failure inside a tool is returned
  as a tool error (`isError`), not a protocol error, so the calling model can
  correct itself.
- **File paths are the caller's.** Tools that take a path open it as the
  process's user. Run the server as an account that can read only what it
  should; the server does not sandbox paths, and a caller who can reach stdin
  is already on the machine.
- **No tool fetches anything.** Nothing here makes a network request.
- **`previous_hash` is validated.** `evaluate_decision` accepts a 64-character
  lowercase hex SHA-256 or null; any other JSON type is refused before a
  Receipt is built, so a chain cannot carry a non-hash where a hash belongs.

Out of scope: the authenticity of a schema or instance the caller supplies is
the caller's problem; the server validates and evaluates what it is given.
