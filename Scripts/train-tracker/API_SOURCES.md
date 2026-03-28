# API Sources and References

This document contains all external API sources, libraries, and documentation used in this project.

## ÖBB / HAFAS API

### Official ÖBB Resources
- **ÖBB Scotty (Official Journey Planner)**: https://www.oebb.at/en/fahrplan/fahrplanauskunft/scottymobil
- **ÖBB API Portal**: https://apiportal.oebb.at/ (Official API portal, may require registration)

### HAFAS API Documentation
- **HAFAS mgate API Endpoint**: `https://fahrplan.oebb.at/bin/mgate.exe`
  - This is the mobile gateway API used by the ÖBB mobile app
  - Requires JSON POST requests with specific authentication and client parameters

- **Unofficial ÖBB API Documentation**: https://github.com/hoenic07/oebb-api-docs
  - Community-maintained documentation for common ÖBB API endpoints
  - Includes examples and parameter descriptions

- **HAFAS Client Documentation** (JavaScript reference): https://github.com/public-transport/hafas-client
  - Generic HAFAS client implementation
  - Useful for understanding HAFAS API structure

- **HAFAS mgate API Technical Docs**: https://github.com/public-transport/hafas-client/blob/main/docs/hafas-mgate-api.md
  - Technical documentation of the mgate.exe protocol
  - Request/response format specifications

### Transport REST APIs (Initially Attempted)
- **ÖBB transport.rest** (NOT WORKING as of March 2026): https://v6.oebb.transport.rest/
  - Documented at: https://oebb.macistry.com/docs
  - GitHub: https://github.com/nocontent06/oebb.transport.rest
  - **Status**: API appears to be non-functional or not fully deployed
  - Documented endpoints return 404 errors

- **DB transport.rest** (Working, for Deutsche Bahn): https://v6.db.transport.rest/
  - Similar API for German railways
  - Different profile/network, not compatible with ÖBB

## Python Libraries

### pyhafas
- **PyPI Package**: https://pypi.org/project/pyhafas/
- **Version Used**: 0.6.1
- **GitHub Repository**: https://github.com/FahrplanDatenGarten/pyhafas
- **Documentation**: https://pyhafas.readthedocs.io/
- **Purpose**: Generic Python client for HAFAS systems
- **License**: GPL-3.0
- **Note**: Does not include ÖBB profile by default (we created a custom one)

### Custom ÖBB Profile
- **File**: `oebb_profile.py` (included in this project)
- **Based on**: pyhafas BaseProfile class
- **API Endpoint**: `https://fahrplan.oebb.at/bin/mgate.exe`
- **Authentication**:
  - Client ID: `OEBB`
  - AID: `OWDL4fE4ixNiPBBm` (from reverse engineering ÖBB Android app)
  - Version: 6140000
- **Salt**: `5DBkaU5t` (for checksum calculation)

## Alternative Implementations (Not Used)

### Node.js Libraries
- **oebb-api** (npm): https://www.npmjs.com/package/oebb-api
  - GitHub: https://github.com/mymro/oebb-api
  - JavaScript/Node.js only

- **oebb** (npm): https://github.com/juliuste/oebb
  - Another JavaScript client for ÖBB HAFAS API

### Other Resources
- **HAFAS Monitor Departures**: https://github.com/derhuerst/hafas-monitor-departures
  - Tool for monitoring departures from multiple stations

- **HAFAS Endpoints List**: https://gist.github.com/derhuerst/2b7ed83bfa5f115125a5
  - List of known HAFAS endpoints across Europe

## OpenHAB Integration

### OpenHAB REST API
- **Official Documentation**: https://www.openhab.org/docs/configuration/restdocs.html
- **API Endpoints Used**:
  - `PUT /rest/items/{itemName}/state` - Update item state

### Authentication
- Uses Bearer token authentication
- Token created in OpenHAB: Settings → API Security → Create API Token

## Technical Details

### HAFAS Request Format
The ÖBB HAFAS API requires POST requests with this structure:

```json
{
  "lang": "deu",
  "client": {
    "id": "OEBB",
    "v": "6140000",
    "type": "AND",
    "name": "oebbPROD-AND"
  },
  "ext": "OEBB.1",
  "ver": "1.57",
  "auth": {
    "type": "AID",
    "aid": "OWDL4fE4ixNiPBBm"
  },
  "svcReqL": [
    {
      "req": { /* specific request data */ },
      "meth": "LocMatch",  // or "StationBoard", "JourneyDetails", etc.
      "id": "1|"
    }
  ]
}
```

### Station ID Format
- ÖBB station IDs are typically 7-digit numbers (e.g., `1290401` for Wien Hbf)
- Can be obtained via `LocMatch` method in HAFAS API

### Product Types (Train Categories)
- `1` - Long Distance Express (RJ/RJX)
- `2` - Long Distance (EC/IC)
- `4` - Regional Express (REX)
- `8` - Regional (R)
- `16` - Suburban (S-Bahn)
- `32` - Bus
- `64` - Ferry
- `128` - Subway (U-Bahn)
- `256` - Tram
- `512` - Taxi

## Troubleshooting Resources

### Common Issues
1. **Station Not Found**:
   - Use exact station names as shown on ÖBB website
   - Try variations (e.g., "Strasshof" vs "Strasshof/Nordbahn")
   - Use `--test-station` flag to test lookups

2. **API Changes**:
   - ÖBB may update their API authentication parameters
   - Check GitHub repositories for updates
   - Monitor HAFAS client libraries for changes

3. **Rate Limiting**:
   - No official rate limits documented
   - Recommend 5-15 minute polling intervals for scheduled use

## Version History

### March 2026
- Initial implementation using pyhafas with custom ÖBB profile
- v6.oebb.transport.rest found to be non-functional
- Created custom OEBBProfile based on HAFAS mgate API

## Contributing

If you find updated API endpoints or authentication parameters:
1. Test them thoroughly
2. Update `oebb_profile.py` with new parameters
3. Document changes in this file
4. Submit pull request or create issue on GitHub

## License Information

- **This Project**: Check main LICENSE file
- **pyhafas**: GPL-3.0 License
- **ÖBB API**: No official public API license (reverse-engineered from mobile app)
- **OpenHAB**: Eclipse Public License 2.0

## Disclaimer

This project uses reverse-engineered ÖBB API endpoints. Use responsibly and in accordance with ÖBB's terms of service. The API may change without notice.

---

**Last Updated**: March 7, 2026
**Maintained By**: Project contributors
**ÖBB API Version**: 1.57 (as of March 2026)
