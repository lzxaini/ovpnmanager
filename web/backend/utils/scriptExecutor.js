const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const SCRIPT_PATH = process.env.OPENVPN_SCRIPT_PATH || '/app/openvpn-install.sh';

/**
 * Execute the OpenVPN installation script with given arguments
 * @param {string[]} args - Command line arguments
 * @returns {Promise<{success: boolean, data?: any, error?: string, output?: string}>}
 */
async function executeScript(args) {
  try {
    const command = `bash ${SCRIPT_PATH} ${args.join(' ')}`;
    console.log('Executing command:', command);

    const { stdout, stderr } = await execPromise(command, {
      env: {
        ...process.env,
        NON_INTERACTIVE_INSTALL: 'y',
        OUTPUT_FORMAT: args.includes('--format') && args[args.indexOf('--format') + 1] === 'json' ? 'json' : 'table'
      },
      maxBuffer: 1024 * 1024 * 10 // 10MB buffer
    });

    // Try to parse JSON output
    if (args.includes('--format') && args[args.indexOf('--format') + 1] === 'json') {
      try {
        const data = JSON.parse(stdout);
        return { success: true, data };
      } catch (e) {
        console.error('Failed to parse JSON output:', e);
        return { success: true, output: stdout };
      }
    }

    return { success: true, output: stdout };
  } catch (error) {
    console.error('Script execution error:', error);
    return {
      success: false,
      error: error.message,
      output: error.stdout,
      stderr: error.stderr
    };
  }
}

module.exports = { executeScript };
