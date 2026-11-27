import { describe, expect, it } from 'vitest'

import { alvoResolucoes } from '../../testes/exemplos.ts'
import { corpoDoFormulario, linhasParaMapa, lista, mapaParaLinhas, valoresIniciais } from './formularioAlvo.ts'

describe('conversões de texto', () => {
  it('linhasParaMapa ignora linhas sem ":" e mantém ":" no valor', () => {
    expect(linhasParaMapa('Norma: norma\n\nsem dois pontos\n Link: http://x:8080 ')).toEqual({ Norma: 'norma', Link: 'http://x:8080' })
  })

  it('mapaParaLinhas e lista', () => {
    expect(mapaParaLinhas({ a: '1', b: '2' })).toBe('a: 1\nb: 2')
    expect(mapaParaLinhas(undefined)).toBe('')
    expect(lista(' norma, ementa ,, ')).toEqual(['norma', 'ementa'])
  })
})

describe('valoresIniciais', () => {
  it('novo alvo', () => {
    const v = valoresIniciais(null)
    expect(v).toMatchObject({ id: '', anos: 'atual', ativo: false, metodo: 'lista_itens', chave_item: 'norma', tabela: 'primeira', colunas: '' })
  })

  it('alvo existente', () => {
    const v = valoresIniciais(alvoResolucoes)
    expect(v).toMatchObject({
      id: 'anac-resolucoes', prioridade: 'alta', anos: 'atual, anterior', ativo: true, regex_numero: 'resolucao',
      colunas: 'Norma: norma\nPublicação: publicacao', marcar_status: 'revogada: revogada', observacoes: 'principal',
    })
  })
})

describe('corpoDoFormulario', () => {
  it('ida e volta sem mudar nada preserva a definição e descarta campos desconhecidos', () => {
    const corpo = corpoDoFormulario(valoresIniciais(alvoResolucoes), alvoResolucoes)
    const { campo_antigo_da_importacao: _descartado, ...esperado } = alvoResolucoes.definicao
    expect(_descartado).toBe('descartar')
    expect(corpo).toEqual(esperado)
    expect(corpo).not.toHaveProperty('campo_antigo_da_importacao')
  })

  it('campos vazios viram os padrões da API', () => {
    const v = { ...valoresIniciais(null), id: ' novo-alvo ', url: ' https://exemplo.com/{ano} ', anos: '', chave_item: ' ' }
    expect(corpoDoFormulario(v, null)).toEqual({
      id: 'novo-alvo', ativo: false, categoria: '', site: '', url: 'https://exemplo.com/{ano}', anos: ['atual'], observacoes: '',
      deteccao: { metodo: 'lista_itens', chave_item: 'norma' },
      extracao: { tabela: 'primeira', colunas: 'auto', marcar_status: {} },
    })
  })

  it('anos numéricos, campos de alteração, colunas e prioridade', () => {
    const v = {
      ...valoresIniciais(null), id: 'x', url: 'https://x', anos: 'atual, 2025', detectar_mudanca_em: 'ementa, publicacao',
      colunas: 'Norma: norma', regex_numero: 'rbac', prioridade: 'baixa' as const, metodo: 'hash_conteudo' as const, tabela: 'todas' as const,
    }
    expect(corpoDoFormulario(v, null)).toMatchObject({
      anos: ['atual', 2025], prioridade: 'baixa',
      deteccao: { metodo: 'hash_conteudo', chave_item: 'norma', detectar_mudanca_em: ['ementa', 'publicacao'] },
      extracao: { tabela: 'todas', colunas: { Norma: 'norma' }, regex_numero: 'rbac' },
    })
  })

  it('tirar a prioridade remove o campo', () => {
    const corpo = corpoDoFormulario({ ...valoresIniciais(alvoResolucoes), prioridade: '' }, alvoResolucoes)
    expect(corpo).not.toHaveProperty('prioridade')
  })
})
