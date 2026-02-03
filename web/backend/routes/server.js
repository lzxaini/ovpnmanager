const express = require('express');
const { body, validationResult } = require('express-validator');
const { authenticateToken } = require('../middleware/auth');
const { executeScript } = require('../utils/scriptExecutor');

const router = express.Router();

// Apply authentication to all routes
router.use(authenticateToken);

/**
 * GET /api/server/status
 * Get OpenVPN server status and connected clients
 */
router.get('/status', async (req, res) => {
  try {
    const result = await executeScript(['server', 'status', '--format', 'json']);

    if (result.success) {
      res.json(result.data);
    } else {
      res.status(500).json({ error: result.error });
    }
  } catch (error) {
    console.error('Server status error:', error);
    res.status(500).json({ error: 'Failed to get server status' });
  }
});

/**
 * POST /api/server/renew
 * Renew server certificate
 */
router.post('/renew',
  [
    body('certDays').optional().isInt({ min: 1 }).withMessage('Certificate days must be positive')
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { certDays } = req.body;

    try {
      const args = ['server', 'renew'];
      
      if (certDays) {
        args.push('--cert-days', certDays.toString());
      }

      const result = await executeScript(args);

      if (result.success) {
        res.json({
          success: true,
          message: 'Server certificate renewed successfully'
        });
      } else {
        res.status(500).json({ error: result.error });
      }
    } catch (error) {
      console.error('Server renew error:', error);
      res.status(500).json({ error: 'Failed to renew server certificate' });
    }
  }
);

/**
 * GET /api/server/info
 * Get OpenVPN installation info
 */
router.get('/info', async (req, res) => {
  try {
    // Check if OpenVPN is installed
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);

    const checks = await Promise.allSettled([
      execPromise('openvpn --version').then(r => r.stdout.split('\n')[0]),
      execPromise('systemctl is-active openvpn-server@server').then(r => r.stdout.trim()),
      execPromise('test -f /etc/openvpn/server/server.conf && echo "installed" || echo "not installed"').then(r => r.stdout.trim())
    ]);

    const version = checks[0].status === 'fulfilled' ? checks[0].value : 'Unknown';
    const serviceStatus = checks[1].status === 'fulfilled' ? checks[1].value : 'inactive';
    const installed = checks[2].status === 'fulfilled' && checks[2].value === 'installed';

    res.json({
      installed,
      version,
      serviceStatus,
      isRunning: serviceStatus === 'active'
    });
  } catch (error) {
    console.error('Server info error:', error);
    res.status(500).json({ error: 'Failed to get server info' });
  }
});

module.exports = router;
