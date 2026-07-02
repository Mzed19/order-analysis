import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
    url: 'https://www.michaeldumontdev.com/auth',
    realm: 'Contract AI',
    clientId: 'contract-ai-web',
});

export default keycloak;