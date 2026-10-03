// Auth stub for pages
export function getAuthHeader(): Record<string, string> {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('sevalor_access_token');
    const user = JSON.parse(localStorage.getItem('sevalor_user') || '{}');
    const empresa_id = user?.empresa_id || localStorage.getItem('sevalor_empresa_id');
    
    return {
      'Authorization': `Bearer ${token}`,
      'X-Empresa-ID': empresa_id || ''
    };
  }
  return {};
}
