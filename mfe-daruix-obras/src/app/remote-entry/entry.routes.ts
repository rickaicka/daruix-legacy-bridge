import { Routes } from '@angular/router';

export const OBRAS_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('../features/obras/pages/obras-list/obras-list').then((m) => m.ObrasList),
  },
  // {
  //   path: 'cadastro-composicao-servico',
  //   loadComponent: () =>
  //     import('../features/composicao-servico/pages/cadastrar-composicao/cadastrar-composicao.component').then(
  //       (m) => m.CadastrarComposicao,
  //     ),
  // },
];
