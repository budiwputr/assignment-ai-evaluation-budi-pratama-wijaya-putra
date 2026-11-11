import sys; sys.path.insert(0,'system')
from app import rag
qs=['Tolong jelaskan sedetail-detailnya seluruh kebijakan cuti','reset password','permintaan perangkat','proses onboarding','kebijakan cuti','permintaan laptop','onboarding karyawan baru','resep rendang','cuaca besok','aturan parkir']
rag.build_index(); v=rag._embed(qs,'RETRIEVAL_QUERY')
s,i=rag._index.search(v,2)
for k,q in enumerate(qs):
    print(q)
    for j in range(2): print('   %.3f faq#%d %s'%(s[k][j],rag._df.iloc[int(i[k][j])]['faq_id'],rag._df.iloc[int(i[k][j])]['question'][:55]))
