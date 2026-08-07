export class CliError extends Error {
  constructor(code, message, status = undefined, details = undefined) {
    super(message);
    this.name = 'CliError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}
