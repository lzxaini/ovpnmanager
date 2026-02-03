const express = require('express');
const { body, validationResult } = require('express-validator');
const { authenticateToken } = require('../middleware/auth');
const { executeScript } = require('../utils/scriptExecutor');
const path = require('path');
const fs = require('fs').promises;

const router = express.Router();

// Apply authentication to all routes
router.use(authenticateToken);

/**
 * GET /api/clients
 * List all OpenVPN clients
 */
router.get('/', async (req, res) => {
  try {
    const result = await executeScript(['client', 'list', '--format', 'json']);
    
    if (result.success) {
      res.json(result.data);
    } else {
      res.status(500).json({ error: result.error });
    }
  } catch (error) {
    console.error('List clients error:', error);
    res.status(500).json({ error: 'Failed to list clients' });
  }
});

/**
 * POST /api/clients
 * Add a new OpenVPN client
 */
router.post('/',
  [
    body('name').trim().notEmpty().withMessage('Client name is required')
      .matches(/^[a-zA-Z0-9_-]+$/).withMessage('Client name can only contain letters, numbers, hyphens and underscores')
      .isLength({ max: 64 }).withMessage('Client name too long (max 64 characters)'),
    body('password').optional().isString(),
    body('certDays').optional().isInt({ min: 1 }).withMessage('Certificate days must be positive')
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { name, password, certDays } = req.body;

    try {
      const args = ['client', 'add', name];
      
      if (password) {
        args.push('--password', password);
      }
      
      if (certDays) {
        args.push('--cert-days', certDays.toString());
      }

      const result = await executeScript(args);

      if (result.success) {
        // Try to get the generated config file path
        let configPath = null;
        const homeDir = process.env.CLIENT_CONFIG_DIR || '/root';
        const possiblePath = path.join(homeDir, `${name}.ovpn`);
        
        try {
          await fs.access(possiblePath);
          configPath = possiblePath;
        } catch (e) {
          // Config file not found at expected location
        }

        res.json({
          success: true,
          message: `Client ${name} created successfully`,
          client: { name, configPath }
        });
      } else {
        res.status(500).json({ error: result.error });
      }
    } catch (error) {
      console.error('Add client error:', error);
      res.status(500).json({ error: 'Failed to add client' });
    }
  }
);

/**
 * DELETE /api/clients/:name
 * Revoke an OpenVPN client
 */
router.delete('/:name', async (req, res) => {
  const { name } = req.params;

  if (!name || !name.match(/^[a-zA-Z0-9_-]+$/)) {
    return res.status(400).json({ error: 'Invalid client name' });
  }

  try {
    const result = await executeScript(['client', 'revoke', name]);

    if (result.success) {
      res.json({
        success: true,
        message: `Client ${name} revoked successfully`
      });
    } else {
      res.status(500).json({ error: result.error });
    }
  } catch (error) {
    console.error('Revoke client error:', error);
    res.status(500).json({ error: 'Failed to revoke client' });
  }
});

/**
 * POST /api/clients/:name/renew
 * Renew an OpenVPN client certificate
 */
router.post('/:name/renew',
  [
    body('certDays').optional().isInt({ min: 1 }).withMessage('Certificate days must be positive')
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { name } = req.params;
    const { certDays } = req.body;

    if (!name || !name.match(/^[a-zA-Z0-9_-]+$/)) {
      return res.status(400).json({ error: 'Invalid client name' });
    }

    try {
      const args = ['client', 'renew', name];
      
      if (certDays) {
        args.push('--cert-days', certDays.toString());
      }

      const result = await executeScript(args);

      if (result.success) {
        res.json({
          success: true,
          message: `Client ${name} renewed successfully`
        });
      } else {
        res.status(500).json({ error: result.error });
      }
    } catch (error) {
      console.error('Renew client error:', error);
      res.status(500).json({ error: 'Failed to renew client' });
    }
  }
);

/**
 * GET /api/clients/:name/config
 * Download client configuration file
 */
router.get('/:name/config', async (req, res) => {
  const { name } = req.params;

  if (!name || !name.match(/^[a-zA-Z0-9_-]+$/)) {
    return res.status(400).json({ error: 'Invalid client name' });
  }

  try {
    const homeDir = process.env.CLIENT_CONFIG_DIR || '/root';
    const configPath = path.join(homeDir, `${name}.ovpn`);

    // Check if file exists
    await fs.access(configPath);

    // Send file
    res.download(configPath, `${name}.ovpn`, (err) => {
      if (err) {
        console.error('Download error:', err);
        if (!res.headersSent) {
          res.status(500).json({ error: 'Failed to download config file' });
        }
      }
    });
  } catch (error) {
    console.error('Config download error:', error);
    res.status(404).json({ error: 'Configuration file not found' });
  }
});

/**
 * POST /api/clients/:name/disconnect
 * Force disconnect a connected client
 */
router.post('/:name/disconnect', async (req, res) => {
  const { name } = req.params;

  if (!name || !name.match(/^[a-zA-Z0-9_-]+$/)) {
    return res.status(400).json({ error: 'Invalid client name' });
  }

  try {
    // Use socat to send kill command to management interface
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);

    const mgmtSocket = '/var/run/openvpn-server/server.sock';
    
    // Check if socket exists
    try {
      await fs.access(mgmtSocket);
    } catch (error) {
      return res.status(503).json({ 
        error: 'Management interface not available',
        details: 'OpenVPN management socket not found. Service may not be running.'
      });
    }

    // Send kill command via management interface
    await execPromise(`echo "kill ${name}" | socat - UNIX-CONNECT:${mgmtSocket}`);

    res.json({
      success: true,
      message: `Client ${name} has been disconnected`
    });
  } catch (error) {
    console.error('Disconnect client error:', error);
    res.status(500).json({ 
      error: 'Failed to disconnect client',
      details: error.message
    });
  }
});

module.exports = router;
