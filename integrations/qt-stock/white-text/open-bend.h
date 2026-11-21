// Restore the middle of an open stroke only where it meets the native stroke at both ends.
bool restoreCompressedTurn(fontreal_v3::OutlineSamples &outline,
                           const fontreal_v3::OutlineSamples &reference, int mode, int &firstRow, int &endRow)
{
    using namespace fontreal_v3;
    if(reference.pixels.empty() || hasSeveralCounters(outline,1))
        return false;
    const int w=outline.frame.width,h=outline.frame.height;
    const int pad=(outline.pitch-4*w)/2;
    struct Slice {int area=0;double center=0;int runs=0;};
    const auto measure=[&](const OutlineSamples &samples,int y) {
        Slice result;
        bool inRun=false;
        for(int x=0;x<w;++x) {
            const int a=samples.center(x,y);
            result.area+=a;
            result.center+=(x+.5)*a;
            if(a>=14 && !inRun)
                ++result.runs;
            inRun=a>=14;
        }
        if(result.area)
            result.center/=result.area;
        return result;
    };
    const auto weak=[&](int y) {
        const auto a=measure(outline,y),b=measure(reference,y);
        return b.area>=172 && b.area<=(mode>=40 ? 590 : 486) && a.area<.72*b.area && b.runs==1;
    };
    const auto contact=[&](int boundary,int outlineRow) {
        int agreement=0;
        for(int x=1;x+1<4*w;++x) {
            const int continuous=std::min(reference.highPixel(x,boundary-1),reference.highPixel(x,boundary));
            const int neighbor=std::max({outline.highPixel(x-1,outlineRow),
                                           outline.highPixel(x,outlineRow),outline.highPixel(x+1,outlineRow)});
            if(std::min(continuous,neighbor)>=43)
                ++agreement;
        }
        return agreement>=1;
    };
    const int low=std::max(2,int(.31*h)),high=std::min(h-2,int(.71*h)+1);
    for(int y=low;y<high;) {
        if(!weak(y)) {
            ++y;
            continue;
        }
        const int first=y++;
        while(y<high && weak(y))
            ++y;
        const bool longerTurn=mode>=33 && y-first==3
                && measure(outline,first+1).area<.61*measure(reference,first+1).area;
        if (y-first>2 && !longerTurn)
            continue;
        for (int end=y;end>first;--end) {
            const auto before=measure(outline,first-1),after=measure(outline,end);
            const double shift=std::abs(before.center-after.center);
            if(before.runs!=1 || after.runs!=1 || before.area<72 || after.area<72
                    || before.area>320 || after.area>(mode>=31 ? 385 : 320) || shift<.8 || shift>((longerTurn && end-first==3) ? (mode>=40 ? 5.65 : 4.70) : 4.15)
                    || !contact(4*first,4*first-1) || !contact(4*end,4*end))
                continue;
            int top=first,bottom=end;
            if(mode>=32) {
                const auto canExtend=[&](int row,int border,int nativeRow) {
                    const auto old=measure(outline,row),guide=measure(reference,row);
                    return old.runs==1 && guide.runs==1 && old.area>=70 && guide.area>=105
                           && guide.area*1.05>=old.area
                           && std::abs(guide.center-old.center)<.64
                           && contact(border,nativeRow);
                };
                if(first>=2 && canExtend(first-1,4*(first-1),4*(first-1)-1))
                    --top;
                if(end+1<h && canExtend(end,4*(end+1),4*(end+1)))
                    ++bottom;
            }
            for(int row=4*top;row<4*bottom;++row) {
                const bool seam=row==4*top || row==4*bottom-1;
                const bool shoulder=row<4*first || row>=4*end;
                const double blend=shoulder ? (seam ? .54 : .78) : seam ? .74 : .94;
                for(int x=0;x<4*w;++x) {
                    auto &a=outline.pixels[(row+pad)*outline.pitch+x+pad];
                    a=Coverage(std::lround(a+blend*(int(reference.highPixel(x,row))-a)));
                }
            }
            firstRow=top;
            endRow=bottom;
            return true;
        }
    }
    return false;
}
