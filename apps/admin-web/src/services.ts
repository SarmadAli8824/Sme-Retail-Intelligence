import {HttpClient, HttpInterceptorFn} from '@angular/common/http';
import {inject, Injectable} from '@angular/core';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = localStorage.getItem('retail_intelligence_token');
  return next(token ? request.clone({setHeaders:{Authorization:`Bearer ${token}`}}) : request);
};

@Injectable({providedIn:'root'})
export class ApiService {
  private http = inject(HttpClient);
  private api = location.hostname === 'localhost' && location.port === '4200' ? 'http://localhost:8000/api/v1' : '/api/v1';
  login(value:unknown){ return this.http.post<any>(this.api + '/auth/login', value); }
  me(){ return this.http.get<any>(this.api + '/auth/me'); }
  users(){ return this.http.get<any[]>(this.api + '/users'); }
  createUser(value:unknown){ return this.http.post(this.api + '/users', value); }
  updateUser(id:string, value:unknown){ return this.http.patch(this.api + '/users/' + id, value); }
  uploads(){ return this.http.get<any[]>(this.api + '/uploads'); }
  upload(kind:'sales'|'inventory', file:File){ const form=new FormData();form.append('file',file);return this.http.post<any>(`${this.api}/uploads/${kind}?background=true`,form); }
  settings(){ return this.http.get<any>(this.api + '/settings'); }
  updateSettings(value:unknown){ return this.http.put<any>(this.api + '/settings', value); }
}
